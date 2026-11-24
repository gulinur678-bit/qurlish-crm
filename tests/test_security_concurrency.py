"""Independent connections and explicit scheduling; never use the demo database."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend import auth, identity
from backend.identity import RefreshSession, User
from backend.main import app
from test_api import _client, _login


@pytest.fixture
def setup(tmp_path):
    client, factory, ids, engine = _client(tmp_path)
    try:
        yield client, factory, ids
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()


def call(path, *, token=None, cookie=None, body=None, method="POST"):
    headers = {}
    if token:
        headers.update(token)
    if cookie:
        headers["Cookie"] = f"{auth.REFRESH_COOKIE}={cookie}"
    with TestClient(app) as client:
        return client.request(method, path, headers=headers, json=body)


def access(response):
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_parallel_refresh_has_one_successor_and_reuse_revokes_family(setup, monkeypatch):
    client, factory, _ = setup
    old_access = _login(client, "seller@test.local")
    cookie = client.cookies.get(auth.REFRESH_COOKIE)
    barrier = Barrier(2)
    original = identity.lock_security_writes

    def simultaneous(session):
        barrier.wait(timeout=10)
        original(session)

    monkeypatch.setattr(identity, "lock_security_writes", simultaneous)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(call, "/api/auth/refresh", cookie=cookie) for _ in range(2)]
        results = [job.result(timeout=15) for job in jobs]
    monkeypatch.setattr(identity, "lock_security_writes", original)
    assert sorted(r.status_code for r in results) == [200, 401]
    winner = next(r for r in results if r.status_code == 200)
    assert call("/api/crm/me", token=old_access, method="GET").status_code == 401
    assert call("/api/crm/me", token=access(winner), method="GET").status_code == 401
    assert call("/api/auth/refresh", cookie=winner.cookies.get(auth.REFRESH_COOKIE)).status_code == 401
    with factory() as session:
        rows = session.scalars(select(RefreshSession)).all()
        assert len(rows) == 2  # original and exactly one successor
        assert all(row.revoked_at is not None for row in rows)


@pytest.mark.parametrize("revocation", ["logout", "deactivate"])
@pytest.mark.parametrize("refresh_first", [True, False])
def test_refresh_cannot_resurrect_revoked_account_or_family(setup, monkeypatch, revocation, refresh_first):
    client, factory, _ = setup
    admin = _login(client, "admin@test.local")
    seller = _login(client, "seller@test.local")
    cookie = client.cookies.get(auth.REFRESH_COOKIE)
    with factory() as session:
        seller_id = session.scalar(select(User.id).where(User.role == "seller"))
    held, contender, release = Event(), Event(), Event()
    guard = Lock()
    count = 0
    original = identity.lock_security_writes

    def scheduled(session):
        nonlocal count
        with guard:
            count += 1
            first = count == 1
        if not first:
            contender.set()
        original(session)
        if first:
            held.set()
            assert release.wait(timeout=10)

    monkeypatch.setattr(identity, "lock_security_writes", scheduled)

    def renew():
        return call("/api/auth/refresh", cookie=cookie)

    def revoke():
        if revocation == "logout":
            return call("/api/auth/logout", cookie=cookie)
        return call(f"/api/admin/users/{seller_id}", token=admin, body={"is_active": False}, method="PATCH")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(renew if refresh_first else revoke)
        try:
            assert held.wait(timeout=10)
            second = pool.submit(revoke if refresh_first else renew)
            assert contender.wait(timeout=10)
        finally:
            release.set()
        results = [first.result(timeout=15), second.result(timeout=15)]
    renewed, revoked = results if refresh_first else results[::-1]
    assert revoked.status_code == 200
    assert renewed.status_code == (200 if refresh_first else 401)
    assert call("/api/crm/me", token=seller, method="GET").status_code == 401
    assert call("/api/auth/refresh", cookie=cookie).status_code == 401
    if refresh_first:
        assert call("/api/crm/me", token=access(renewed), method="GET").status_code == 401
        assert call("/api/auth/refresh", cookie=renewed.cookies.get(auth.REFRESH_COOKIE)).status_code == 401
    if revocation == "deactivate":
        assert call(f"/api/admin/users/{seller_id}", token=admin, body={"is_active": True}, method="PATCH").status_code == 200
        assert call("/api/crm/me", token=seller, method="GET").status_code == 401
        assert call("/api/auth/refresh", cookie=cookie).status_code == 401


def test_bearer_only_logout_revokes_only_its_family(setup):
    client, _, _ = setup
    first = _login(client, "seller@test.local")
    first_cookie = client.cookies.get(auth.REFRESH_COOKIE)
    second = _login(client, "seller@test.local")
    assert call("/api/auth/logout", token=first).status_code == 200
    assert call("/api/auth/logout", token=first).status_code == 200
    assert call("/api/crm/me", token=first, method="GET").status_code == 401
    assert call("/api/auth/refresh", cookie=first_cookie).status_code == 401
    assert call("/api/crm/me", token=second, method="GET").status_code == 200


def test_failed_rotation_rolls_back_consumption(setup, monkeypatch):
    client, factory, _ = setup
    old_access = _login(client, "seller@test.local")
    cookie = client.cookies.get(auth.REFRESH_COOKIE)
    original = auth.add_audit

    def fail_after_claim(*args, **kwargs):
        raise RuntimeError("injected transaction failure")

    monkeypatch.setattr(auth, "add_audit", fail_after_claim)
    with TestClient(app, raise_server_exceptions=False) as failed:
        response = failed.post("/api/auth/refresh", headers={"Cookie": f"{auth.REFRESH_COOKIE}={cookie}"})
    assert response.status_code == 500
    with factory() as session:
        rows = session.scalars(select(RefreshSession)).all()
        assert len(rows) == 1 and rows[0].used_at is None
    monkeypatch.setattr(auth, "add_audit", original)
    assert call("/api/auth/refresh", cookie=cookie).status_code == 200
    assert call("/api/crm/me", token=old_access, method="GET").status_code == 200


def test_auth_responses_are_not_cacheable(setup):
    client, _, _ = setup
    _login(client, "viewer@test.local")
    response = client.post("/api/auth/refresh")
    assert response.headers["Cache-Control"] == "no-store"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]


def test_deactivation_and_role_change_revoke_all_user_families(setup):
    client, factory, _ = setup
    admin = _login(client, "admin@test.local")
    with factory() as session:
        seller_id = session.scalar(select(User.id).where(User.role == "seller"))
    for change in ({"role": "viewer"}, {"is_active": False}):
        tokens, cookies = [], []
        for _ in range(2):
            tokens.append(_login(client, "seller@test.local"))
            cookies.append(client.cookies.get(auth.REFRESH_COOKIE))
        assert call(f"/api/admin/users/{seller_id}", token=admin, body=change, method="PATCH").status_code == 200
        for token, cookie in zip(tokens, cookies):
            assert call("/api/crm/me", token=token, method="GET").status_code == 401
            assert call("/api/auth/refresh", cookie=cookie).status_code == 401
    assert client.post("/api/auth/login", json={"email": "seller@test.local", "password": "safe-test-password-123"}).status_code == 401
    assert call("/api/crm/me", token=admin, method="GET").status_code == 200


def test_foreign_company_user_lead_and_tokens_are_inaccessible(setup):
    client, factory, (_, foreign_lead) = setup
    with factory.begin() as session:
        foreign = User(email="foreign@test.local", password_hash=auth.hash_password("safe-test-password-123"), role="admin", company_id="other-co")
        session.add(foreign)
        session.flush()
        foreign_id = foreign.id
    admin = _login(client, "admin@test.local")
    assert call(f"/api/admin/users/{foreign_id}", token=admin, body={"is_active": False}, method="PATCH").status_code == 404
    assert call(f"/api/crm/leads/{foreign_lead}/notes", token=admin, body={"note": "test"}).status_code == 404
    assert foreign_id not in [u["id"] for u in call("/api/admin/users", token=admin, method="GET").json()["users"]]
    assert client.post("/api/auth/login", json={"email": "foreign@test.local", "password": "safe-test-password-123"}).status_code == 401
    # Correct signature alone is insufficient: company and server-side session matter.
    import jwt
    from backend.config import settings
    original = admin["Authorization"].split()[1]
    payload = jwt.decode(original, settings.jwt_secret, algorithms=["HS256"])
    for changed in ({"company_id": "other-co"}, {"sub": str(foreign_id)}, {"sid": "nonexistent"}, {"exp": 1}):
        forged = jwt.encode({**payload, **changed}, settings.jwt_secret, algorithm="HS256")
        assert call("/api/crm/me", token={"Authorization": f"Bearer {forged}"}, method="GET").status_code == 401


def test_parallel_admin_demotions_keep_one_admin(setup, monkeypatch):
    client, factory, _ = setup
    first = _login(client, "admin@test.local")
    created = client.post("/api/admin/users", headers=first, json={"email": "second@test.local", "password": "safe-test-password-123", "role": "admin"})
    assert created.status_code == 201
    second_id = created.json()["id"]
    second = _login(client, "second@test.local")
    with factory() as session:
        first_id = session.scalar(select(User.id).where(User.email == "admin@test.local"))
    barrier = Barrier(2)
    original = identity.lock_security_writes

    def simultaneous(session):
        barrier.wait(timeout=10)
        original(session)

    monkeypatch.setattr(identity, "lock_security_writes", simultaneous)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(call, f"/api/admin/users/{uid}", token=token, body={"role": "seller"}, method="PATCH") for uid, token in ((first_id, first), (second_id, second))]
        codes = sorted(job.result(timeout=15).status_code for job in jobs)
    assert codes == [200, 409]
    with factory() as session:
        assert len(session.scalars(select(User).where(User.role == "admin", User.is_active.is_(True))).all()) == 1
