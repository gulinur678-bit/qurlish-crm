"""One-time creation of the first administrator; never runs during app startup."""

import os
import re
import sys

from sqlalchemy import select

from .auth import hash_password
from .config import settings
from .identity import Company, SessionLocal, User, add_audit, lock_security_writes


def main() -> int:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        print("Set a valid BOOTSTRAP_ADMIN_EMAIL before running bootstrap.", file=sys.stderr)
        return 2
    if len(password) < 16:
        print("Set BOOTSTRAP_ADMIN_PASSWORD to at least 16 characters.", file=sys.stderr)
        return 2

    with SessionLocal.begin() as session:
        lock_security_writes(session)
        company = session.get(Company, settings.company_id)
        if company is None:
            print("Company row is missing; run `alembic upgrade head` first.", file=sys.stderr)
            return 2
        existing = session.scalar(select(User).where(User.role == "admin", User.company_id == company.id))
        if existing is not None:
            print("An administrator already exists; bootstrap is one-time only.", file=sys.stderr)
            return 2
        admin = User(
            email=email,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
            company_id=company.id,
        )
        session.add(admin)
        session.flush()
        add_audit(session, company_id=company.id, user_id=admin.id, action="bootstrap_admin_created", resource_type="user", resource_id=admin.id)
    print(f"Created the first administrator for company {settings.company_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
