import os

os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-characters-long-123")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.auth import hash_password
from backend.identity import Base, Company, Lead, LeadEvent, RefreshSession, Unit, User, get_db
from backend.main import app


def _login(client: TestClient, email: str, password: str = "safe-test-password-123") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed(session):
    session.add_all(
        [
            Company(id="qurlish", name="Qurlish"),
            Company(id="other-co", name="Other company"),
            Unit(id="A-101", building="A", floor=1, number=1, rooms=2, area=55.5, price=1_000_000, status="available", company_id="qurlish"),
            Unit(id="A-102", building="A", floor=1, number=2, rooms=3, area=75.2, price=2_000_000, status="sold", company_id="qurlish"),
            Unit(id="B-101", building="B", floor=1, number=1, rooms=2, area=55.5, price=1_000_000, status="available", company_id="other-co"),
            User(email="admin@test.local", password_hash=hash_password("safe-test-password-123"), role="admin", company_id="qurlish"),
            User(email="seller@test.local", password_hash=hash_password("safe-test-password-123"), role="seller", company_id="qurlish"),
            User(email="viewer@test.local", password_hash=hash_password("safe-test-password-123"), role="viewer", company_id="qurlish"),
        ]
    )
    session.flush()
    lead = Lead(unit_id="A-101", name="Sinov xaridor", phone="+998901234567", stage="new", company_id="qurlish")
    foreign_lead = Lead(unit_id="B-101", name="Begona xaridor", phone="+998901234568", stage="new", company_id="other-co")
    session.add_all([lead, foreign_lead])
    session.flush()
    session.add(LeadEvent(lead_id=lead.id, actor="public", kind="created", value="Murojaat kelib tushdi", company_id="qurlish"))
    session.add(LeadEvent(lead_id=foreign_lead.id, actor="public", kind="created", value="Other company", company_id="other-co"))
    session.commit()
    return lead.id, foreign_lead.id


def _client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api-test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        ids = _seed(session)

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), factory, ids, engine


def test_public_inventory_and_auth_requirements(tmp_path):
    client, factory, _, engine = _client(tmp_path)
    try:
        assert client.get("/api/public/units").status_code == 200
        assert len(client.get("/api/public/units").json()["units"]) == 2
        assert client.get("/api/crm/leads").status_code == 401
        assert client.post("/api/auth/login", json={"email": "admin@test.local", "password": "wrong"}).status_code == 401
        token = _login(client, "admin@test.local")
        assert client.get("/api/crm/me", headers=token).json()["role"] == "admin"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_public_lead_idempotency_and_metrics(tmp_path):
    client, factory, _, engine = _client(tmp_path)
    try:
        key = "12345678-1234-1234-1234-123456789012"
        data = {"unit_id": "A-101", "name": "Yangi xaridor", "phone": "+998901234567"}
        first = client.post("/api/public/leads", json=data, headers={"Idempotency-Key": key})
        assert first.status_code == 201, first.text
        duplicate = client.post("/api/public/leads", json=data, headers={"Idempotency-Key": key})
        assert duplicate.json() == {"id": first.json()["id"], "duplicate": True}
        assert client.post("/api/public/leads", json={**data, "name": "Boshqa"}, headers={"Idempotency-Key": key}).status_code == 409
        assert client.post("/api/public/leads", json={**data, "unit_id": "A-102"}, headers={"Idempotency-Key": "abcdefab-1234-1234-1234-123456789012"}).status_code == 409
        assert client.post("/api/public/leads", json=data).status_code == 400
        headers = _login(client, "admin@test.local")
        metrics = client.get("/api/crm/metrics?days=30", headers=headers).json()
        assert metrics["count"] == 2
        assert sum(metrics["bins"]) == metrics["count"]
        assert sum(metrics["stages"].values()) == metrics["count"]
        assert metrics["unit_statuses"]["sold"] == 1
        assert client.patch("/api/crm/units/A-101", json={"status": "sold"}, headers=headers).status_code == 409
        assert client.patch("/api/crm/leads/1/stage", json={"stage": "qualified"}, headers=headers).status_code == 200
        assert client.post("/api/crm/leads/1/notes", json={"note": "Ichki xabar"}, headers=headers).status_code == 201
        assert len(client.get("/api/crm/leads/1/events", headers=headers).json()) == 3
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_rbac_and_company_boundary(tmp_path):
    client, factory, (_, foreign_lead_id), engine = _client(tmp_path)
    try:
        viewer = _login(client, "viewer@test.local")
        assert client.get("/api/crm/leads", headers=viewer).status_code == 200
        assert client.patch("/api/crm/leads/1/stage", json={"stage": "qualified"}, headers=viewer).status_code == 403
        assert client.post("/api/crm/leads/1/notes", json={"note": "Viewer yozmasligi kerak"}, headers=viewer).status_code == 403
        assert client.patch("/api/crm/units/A-101", json={"status": "reserved"}, headers=viewer).status_code == 403

        seller = _login(client, "seller@test.local")
        assert client.patch(f"/api/crm/leads/{foreign_lead_id}/stage", json={"stage": "qualified"}, headers=seller).status_code == 404
        assert client.get(f"/api/crm/leads/{foreign_lead_id}/events", headers=seller).status_code == 404
        assert client.patch("/api/crm/units/B-101", json={"status": "reserved"}, headers=_login(client, "admin@test.local")).status_code == 404
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_refresh_rotation_reuse_revokes_session(tmp_path):
    client, factory, _, engine = _client(tmp_path)
    try:
        first = client.post("/api/auth/login", json={"email": "seller@test.local", "password": "safe-test-password-123"})
        assert first.status_code == 200
        original_refresh = client.cookies.get("qurlish_refresh")
        first_access = first.json()["access_token"]
        assert original_refresh
        with factory() as session:
            stored_hashes = set(session.scalars(select(RefreshSession.token_hash)).all())
        import hashlib
        assert hashlib.sha256(original_refresh.encode()).hexdigest() in stored_hashes
        assert original_refresh not in stored_hashes

        rotated = client.post("/api/auth/refresh")
        assert rotated.status_code == 200, rotated.text
        second_refresh = client.cookies.get("qurlish_refresh")
        assert second_refresh != original_refresh
        assert rotated.json()["access_token"] != first_access

        client.cookies.set("qurlish_refresh", original_refresh, path="/api/auth")
        replay = client.post("/api/auth/refresh")
        assert replay.status_code == 401
        client.cookies.set("qurlish_refresh", second_refresh, path="/api/auth")
        assert client.post("/api/auth/refresh").status_code == 401
        assert client.get("/api/crm/me", headers={"Authorization": f"Bearer {first_access}"}).status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_deactivated_account_revokes_existing_access_token(tmp_path):
    client, factory, _, engine = _client(tmp_path)
    try:
        headers = _login(client, "seller@test.local")
        assert client.get("/api/crm/leads", headers=headers).status_code == 200
        with factory.begin() as session:
            seller = session.query(User).filter_by(email="seller@test.local").one()
            seller.is_active = False
        assert client.get("/api/crm/leads", headers=headers).status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_admin_can_create_and_deactivate_user(tmp_path):
    client, factory, _, engine = _client(tmp_path)
    try:
        admin_headers = _login(client, "admin@test.local")
        created = client.post(
            "/api/admin/users",
            json={"email": "new.viewer@test.local", "password": "new-safe-password-123", "role": "viewer"},
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text
        assert created.json()["is_active"] is True
        viewer_headers = _login(client, "new.viewer@test.local", "new-safe-password-123")
        assert client.get("/api/crm/leads", headers=viewer_headers).status_code == 200
        deactivated = client.patch(f"/api/admin/users/{created.json()['id']}", json={"is_active": False}, headers=admin_headers)
        assert deactivated.json()["is_active"] is False
        assert client.get("/api/crm/leads", headers=viewer_headers).status_code == 401
        assert client.get("/api/admin/users", headers=admin_headers).status_code == 200
        assert client.patch("/api/admin/users/1", json={"is_active": False}, headers=admin_headers).status_code == 409
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_cross_origin_write_is_rejected(tmp_path):
    client, factory, _, engine = _client(tmp_path)
    try:
        response = client.post(
            "/api/public/leads",
            json={"unit_id": "A-101", "name": "Test User", "phone": "+998901234567"},
            headers={"Origin": "https://malicious.example", "Idempotency-Key": "12345678-aaaa-bbbb-cccc-123456789012"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_static_site_does_not_expose_repository_files(tmp_path):
    client, factory, _, engine = _client(tmp_path)
    try:
        assert client.get("/").status_code == 200
        assert client.get("/app.js").status_code == 200
        assert client.get("/.env.example").status_code == 404
        assert client.get("/backend/auth.py").status_code == 404
        assert client.get("/README.md").status_code == 404
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
