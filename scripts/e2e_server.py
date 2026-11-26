"""Playwright-only backend: fresh temporary migrated DB and synthetic accounts."""

import os
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if os.environ.get("E2E_TEST_ONLY") != "1" or not os.environ.get("E2E_PASSWORD"):
        raise SystemExit("Run through the Playwright configuration.")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="qurlish-e2e-") as folder:
        database = Path(folder) / "browser.db"
        copy_demo = os.environ.get("E2E_DEMO_COPY") == "1"
        if copy_demo:
            source = ROOT / "demo_data/qurlish_demo.db"
            if source.is_symlink() or not source.is_file():
                raise SystemExit("Expected a local demo file.")
            with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original, sqlite3.connect(database) as clone:
                original.backup(clone)
            with sqlite3.connect(database) as clone:
                assert clone.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        os.environ.update(DATABASE_URL="sqlite:///" + str(database), JWT_SECRET=secrets.token_urlsafe(48), COMPANY_ID="qurlish", COOKIE_SECURE="0")
        from alembic import command
        from alembic.config import Config
        from backend.auth import hash_password
        from backend.identity import Lead, SessionLocal, Unit, User
        from sqlalchemy import select
        import uvicorn
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        with SessionLocal.begin() as session:
            for role in ("admin", "seller", "viewer"):
                session.add(User(email=f"{role}@e2e.test", password_hash=hash_password(os.environ["E2E_PASSWORD"]), role=role, company_id="qurlish"))
            if not copy_demo:
                session.add(Unit(id="A-101", building="A", floor=1, number=1, rooms=2, area=55.5, price=1000000, status="available", company_id="qurlish"))
            session.flush()
            unit_id = session.scalar(select(Unit.id).where(Unit.company_id == "qurlish", Unit.status == "available").order_by(Unit.id))
            assert unit_id is not None
            session.add(Lead(unit_id=unit_id, name="E2E xaridor", phone="+998900000001", stage="new", company_id="qurlish"))
        uvicorn.run("backend.main:app", host="127.0.0.1", port=int(os.environ.get("E2E_API_PORT", "8000")), access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
