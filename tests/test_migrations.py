from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
    insert,
    select,
)


def test_legacy_data_is_preserved_and_roles_are_mapped(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.sqlite"
    url = f"sqlite:///{database_path}"
    engine = create_engine(url)
    metadata = MetaData()
    units = Table(
        "units", metadata,
        Column("id", String(20), primary_key=True), Column("building", String(4)), Column("floor", Integer),
        Column("number", Integer), Column("rooms", Integer), Column("area", Float), Column("price", Integer), Column("status", String(20)),
    )
    staff = Table("staff", metadata, Column("id", Integer, primary_key=True), Column("email", String(200), unique=True), Column("password_hash", String(300)), Column("role", String(20)))
    leads = Table(
        "leads", metadata, Column("id", Integer, primary_key=True), Column("unit_id", String(20), ForeignKey("units.id")),
        Column("name", String(100)), Column("phone", String(24)), Column("stage", String(20)), Column("created_at", DateTime(timezone=True)),
    )
    events = Table(
        "lead_events", metadata, Column("id", Integer, primary_key=True), Column("lead_id", Integer, ForeignKey("leads.id")),
        Column("actor", String(200)), Column("kind", String(30)), Column("value", String(2000)), Column("created_at", DateTime(timezone=True)),
    )
    idempotency = Table("idempotency", metadata, Column("key", String(128), primary_key=True), Column("payload_hash", String(64)), Column("lead_id", Integer, ForeignKey("leads.id")))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(insert(units), {"id": "A-101", "building": "A", "floor": 1, "number": 1, "rooms": 2, "area": 55.5, "price": 1_000_000, "status": "available"})
        connection.execute(insert(staff), [
            {"id": 10, "email": "manager@example.test", "password_hash": "argon2-preserved", "role": "manager"},
            {"id": 11, "email": "root@example.test", "password_hash": "argon2-admin", "role": "admin"},
            {"id": 12, "email": "unknown@example.test", "password_hash": "argon2-unknown", "role": "superuser"},
        ])
        created_at = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
        connection.execute(insert(leads), {"id": 25, "unit_id": "A-101", "name": "Existing lead", "phone": "+998901234567", "stage": "new", "created_at": created_at})
        connection.execute(insert(events), {"id": 30, "lead_id": 25, "actor": "public", "kind": "created", "value": "Murojaat kelib tushdi", "created_at": created_at})
        connection.execute(insert(idempotency), {"key": "legacy-key-12345678", "payload_hash": "a" * 64, "lead_id": 25})

    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")

    migrated = create_engine(url)
    with migrated.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        assert {"companies", "users", "units", "leads", "lead_events", "idempotency", "audit_logs", "refresh_sessions"}.issubset(tables)
        migrated_metadata = MetaData()
        migrated_units = Table("units", migrated_metadata, autoload_with=connection)
        migrated_leads = Table("leads", migrated_metadata, autoload_with=connection)
        migrated_idempotency = Table("idempotency", migrated_metadata, autoload_with=connection)
        audit_logs = Table("audit_logs", migrated_metadata, autoload_with=connection)
        unit = connection.execute(select(migrated_units.c.id, migrated_units.c.company_id).where(migrated_units.c.id == "A-101")).one()
        lead = connection.execute(select(migrated_leads.c.id, migrated_leads.c.company_id).where(migrated_leads.c.id == 25)).one()
        users = Table("users", migrated_metadata, autoload_with=connection)
        mapped = {row.email: row for row in connection.execute(select(users)).all()}
        assert unit.id == "A-101" and unit.company_id == "qurlish"
        assert lead.id == 25 and lead.company_id == "qurlish"
        assert mapped["manager@example.test"].role == "seller"
        assert mapped["manager@example.test"].password_hash == "argon2-preserved"
        assert mapped["root@example.test"].role == "admin"
        assert mapped["unknown@example.test"].role == "viewer"
        assert mapped["unknown@example.test"].is_active is False
        assert connection.execute(select(migrated_idempotency.c.key).where(migrated_idempotency.c.key == "legacy-key-12345678")).first()
        actions = set(connection.execute(select(audit_logs.c.action)).scalars())
        assert "legacy_role_mapped" in actions and "legacy_role_deactivated" in actions
    migrated.dispose()
    engine.dispose()


def test_fresh_database_migrates_without_create_all(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'fresh.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        assert {"companies", "users", "units", "leads", "lead_events", "idempotency", "audit_logs", "refresh_sessions"}.issubset(tables)
        assert connection.execute(select(Table("companies", MetaData(), autoload_with=connection).c.id)).scalar_one() == "qurlish"
    engine.dispose()
