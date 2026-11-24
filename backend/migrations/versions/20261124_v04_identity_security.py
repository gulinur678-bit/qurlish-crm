"""Add identity, refresh sessions, audit history and single-company scoping.

Revision ID: 20261124_v04
Revises:
Create Date: 2026-11-24
"""

from alembic import op
import sqlalchemy as sa
import os
import json


revision = "20261124_v04"
down_revision = None
branch_labels = None
depends_on = None

COMPANY_ID = os.getenv("COMPANY_ID", "qurlish")
COMPANY_NAME = os.getenv("COMPANY_NAME", "Qurlish Construction")


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _ensure_legacy_tables() -> None:
    if not _has_table("units"):
        op.create_table(
            "units",
            sa.Column("id", sa.String(20), primary_key=True),
            sa.Column("building", sa.String(4), nullable=False),
            sa.Column("floor", sa.Integer(), nullable=False),
            sa.Column("number", sa.Integer(), nullable=False),
            sa.Column("rooms", sa.Integer(), nullable=False),
            sa.Column("area", sa.Float(), nullable=False),
            sa.Column("price", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        )
    if not _has_table("staff") and not _has_table("users"):
        op.create_table(
            "staff",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(200), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(300), nullable=False),
            sa.Column("role", sa.String(20), nullable=False, server_default="manager"),
        )
    if not _has_table("leads"):
        op.create_table(
            "leads",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("unit_id", sa.String(20), sa.ForeignKey("units.id"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("phone", sa.String(24), nullable=False),
            sa.Column("stage", sa.String(20), nullable=False, server_default="new"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not _has_table("lead_events"):
        op.create_table(
            "lead_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
            sa.Column("actor", sa.String(200), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("value", sa.String(2000), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not _has_table("idempotency"):
        op.create_table(
            "idempotency",
            sa.Column("key", sa.String(128), primary_key=True),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        )


def _scope_table(table_name: str) -> None:
    op.add_column(table_name, sa.Column("company_id", sa.String(64), nullable=True))
    op.execute(sa.text(f"UPDATE {table_name} SET company_id = :company_id WHERE company_id IS NULL").bindparams(company_id=COMPANY_ID))
    with op.batch_alter_table(table_name) as batch:
        batch.alter_column("company_id", existing_type=sa.String(64), nullable=False)
        batch.create_foreign_key(f"fk_{table_name}_company_id_companies", "companies", ["company_id"], ["id"])
        batch.create_index(f"ix_{table_name}_company_id", ["company_id"])


def upgrade() -> None:
    _ensure_legacy_tables()

    if not _has_table("companies"):
        op.create_table(
            "companies",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
        )
    bind = op.get_bind()
    company_exists = bind.execute(sa.text("SELECT id FROM companies WHERE id = :company_id"), {"company_id": COMPANY_ID}).first()
    if company_exists is None:
        bind.execute(
            sa.text("INSERT INTO companies (id, name) VALUES (:company_id, :name)"),
            {"company_id": COMPANY_ID, "name": COMPANY_NAME},
        )

    if _has_table("staff"):
        op.rename_table("staff", "users")
    op.add_column("users", sa.Column("company_id", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE users SET company_id = :company_id WHERE company_id IS NULL").bindparams(company_id=COMPANY_ID))
    op.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    legacy_roles = bind.execute(sa.text("SELECT id, role FROM users")).mappings().all()
    op.execute("UPDATE users SET role = lower(role)")
    op.execute("UPDATE users SET role = 'seller' WHERE role = 'manager'")
    op.execute("UPDATE users SET role = 'viewer', is_active = FALSE WHERE role NOT IN ('admin', 'seller', 'viewer')")
    with op.batch_alter_table("users") as batch:
        batch.alter_column("company_id", existing_type=sa.String(64), nullable=False)
        batch.alter_column("is_active", existing_type=sa.Boolean(), server_default=None)
        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.create_foreign_key("fk_users_company_id_companies", "companies", ["company_id"], ["id"])
        batch.create_index("ix_users_company_id", ["company_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    for table_name in ("units", "leads", "lead_events", "idempotency"):
        _scope_table(table_name)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("company_id", sa.String(64), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_company_id", "audit_logs", ["company_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    for legacy_user in legacy_roles:
        old_role = (legacy_user["role"] or "").lower()
        if old_role == "manager" or old_role not in {"admin", "seller", "viewer"}:
            new_role = "seller" if old_role == "manager" else "viewer"
            action = "legacy_role_mapped" if old_role == "manager" else "legacy_role_deactivated"
            bind.execute(
                sa.text("""INSERT INTO audit_logs (user_id, company_id, action, resource_type, resource_id, details, created_at)
                          VALUES (:user_id, :company_id, :action, 'user', :resource_id, :details, CURRENT_TIMESTAMP)"""),
                {
                    "user_id": legacy_user["id"],
                    "company_id": COMPANY_ID,
                    "action": action,
                    "resource_id": str(legacy_user["id"]),
                    "details": json.dumps({"from": old_role or None, "to": new_role}, sort_keys=True),
                },
            )
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", sa.String(64), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("token_hash", name="uq_refresh_sessions_token_hash"),
    )
    op.create_index("ix_refresh_sessions_family_id", "refresh_sessions", ["family_id"])
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_company_id", "refresh_sessions", ["company_id"])


def downgrade() -> None:
    raise RuntimeError("v0.4 identity migration is forward-only to prevent dropping audit/session data and weakening migrated roles.")
