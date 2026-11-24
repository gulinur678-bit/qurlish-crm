from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend import bootstrap
from backend.identity import Base, Company, User


def test_parallel_bootstrap_creates_only_one_admin(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as session:
        session.add(Company(id="qurlish", name="Test"))
    monkeypatch.setattr(bootstrap, "SessionLocal", factory)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "bootstrap@test.local")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "long-test-bootstrap-password")
    barrier = Barrier(2)
    original = bootstrap.lock_security_writes

    def simultaneous(session):
        barrier.wait(timeout=10)
        original(session)

    monkeypatch.setattr(bootstrap, "lock_security_writes", simultaneous)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(bootstrap.main) for _ in range(2)]
            assert sorted(job.result(timeout=15) for job in jobs) == [0, 2]
        with factory() as session:
            assert len(session.scalars(select(User)).all()) == 1
    finally:
        engine.dispose()
