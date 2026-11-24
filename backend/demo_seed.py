"""Explicit demo-only seed; requires an already migrated SQLite database."""

import os

from sqlalchemy import func, select

from .auth import hash_password
from .config import settings
from .identity import Company, SessionLocal, Unit, User, engine


if os.getenv("DEMO_DATABASE_ONLY") != "1" or not str(engine.url).startswith("sqlite"):
    raise SystemExit("Refused: DEMO_DATABASE_ONLY=1 and SQLite DATABASE_URL required")

with SessionLocal.begin() as session:
    company = session.get(Company, settings.company_id)
    if company is None:
        raise SystemExit("Run `alembic upgrade head` before demo seed")
    if session.scalar(select(func.count()).select_from(Unit).where(Unit.company_id == company.id)):
        raise SystemExit("Existing inventory: refusing seed")
    for building in "ABCD":
        for floor in range(1, 8):
            for number in range(1, 4):
                session.add(
                    Unit(
                        id=f"{building}-{floor}0{number}",
                        building=building,
                        floor=floor,
                        number=number,
                        rooms=number + 1,
                        area=round(41 + number * 16 + floor * 0.7, 1),
                        price=(650 + number * 120 + floor * 10) * 1_000_000,
                        status="sold" if (ord(building) + floor + number) % 13 == 0 else ("reserved" if (ord(building) + floor + number) % 9 == 0 else "available"),
                        company_id=company.id,
                    )
                )
    email = os.getenv("DEMO_ADMIN_EMAIL", "admin@example.test").strip().lower()
    password = os.getenv("DEMO_ADMIN_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Set DEMO_ADMIN_PASSWORD (minimum 12 characters)")
    if session.scalar(select(User).where(User.email == email)):
        raise SystemExit("Demo admin already exists; refusing duplicate seed")
    session.add(User(email=email, password_hash=hash_password(password), role="admin", company_id=company.id))

print("Seeded 84 demo units and 1 admin (demo SQLite database only)")
