"""Migrate a disposable copy of a SQLite backup, never the source or backup.

Usage: python scripts/verify_demo_migration.py backups/<review>/demo-before-v04.db
Print only counts/check results, never credentials or customer data.
"""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readonly(path):
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)


def main():
    os.umask(0o077)
    backup = Path(sys.argv[1]).resolve(strict=True)
    if not backup.is_relative_to(ROOT / "backups"):
        raise SystemExit("Use a backup inside the ignored backups directory.")
    manifest = json.loads((backup.parent / "manifest.json").read_text())
    source = Path(manifest["source"])
    assert digest(source) == manifest["source_sha256"], "Source changed since backup; take a new backup."
    assert digest(backup) == manifest["backup_sha256"], "Backup changed."
    trial = backup.with_name(f"migration-trial-{uuid4().hex[:8]}.db")
    with readonly(backup) as before, sqlite3.connect(trial) as destination:
        before.backup(destination)
    os.environ["DATABASE_URL"] = "sqlite:///" + str(trial)
    os.environ["COMPANY_ID"] = "qurlish"
    from alembic import command
    from alembic.config import Config
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    summary = {}
    with readonly(backup) as before, readonly(trial) as after:
        for table in ("units", "leads", "lead_events", "idempotency", "staff"):
            columns = [row[1] for row in before.execute(f'PRAGMA table_info("{table}")')]
            projection = ",".join(f'"{col}"' for col in columns)
            target = "users" if table == "staff" else table
            old_rows = before.execute(f'SELECT {projection} FROM "{table}" ORDER BY 1').fetchall()
            new_rows = after.execute(f'SELECT {projection} FROM "{target}" ORDER BY 1').fetchall()
            if table == "staff":
                role_index = columns.index("role")
                expected = []
                for original in old_rows:
                    row = list(original)
                    role = (row[role_index] or "").lower()
                    row[role_index] = "seller" if role == "manager" else role if role in {"admin", "seller", "viewer"} else "viewer"
                    expected.append(tuple(row))
                assert expected == new_rows, "Account fields changed unexpectedly."
            else:
                assert old_rows == new_rows, "Legacy data changed."
            summary[target] = len(new_rows)
            assert after.execute(f'SELECT count(*) FROM "{target}" WHERE company_id != ?', ("qurlish",)).fetchone()[0] == 0
        summary["active_admins"] = after.execute("SELECT count(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0]
        assert summary["active_admins"] == manifest["counts"]["admins"]
        assert after.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert after.execute("PRAGMA foreign_key_check").fetchall() == []
        assert after.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20261124_v04"
        logical_before = list(after.iterdump())
    command.upgrade(config, "head")
    with readonly(trial) as after:
        assert logical_before == list(after.iterdump()), "Second upgrade changed data."
    assert digest(source) == manifest["source_sha256"], "Source changed during verification."
    assert digest(backup) == manifest["backup_sha256"], "Backup was modified."
    result = {"trial": str(trial.relative_to(ROOT)), "preserved": summary, "legacy_fields_and_account_hashes": "equal", "integrity": "ok", "foreign_keys": "ok", "second_upgrade": "no change", "source_and_backup": "unchanged"}
    (backup.parent / "verification.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
