"""Check running demo; load the existing admin password privately if supplied."""

import json
import os
from pathlib import Path
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = os.environ.copy()
    env.pop("DEMO_ADMIN_EMAIL", None)
    env.pop("DEMO_ADMIN_PASSWORD", None)
    credential = ROOT / "backups/admin-login.json"
    if credential.exists():
        if credential.is_symlink():
            raise SystemExit("Credential file cannot be a symlink.")
        os.chmod(credential, 0o600)
        try:
            password = json.loads(credential.read_text())["password"]
            if not isinstance(password, str) or not password:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise SystemExit("Invalid credential file; its contents were not printed.")
        database = ROOT / "demo_data/qurlish_demo.db"
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            admins = connection.execute("SELECT email FROM users WHERE role='admin' AND is_active=1 AND company_id='qurlish'").fetchall()
        if len(admins) != 1:
            raise SystemExit("Expected exactly one existing admin; no password was changed.")
        env.update(DEMO_ADMIN_EMAIL=admins[0][0], DEMO_ADMIN_PASSWORD=password)
    env["NODE_OPTIONS"] = "--use-bundled-ca"
    result = subprocess.run(["node", str(ROOT / "frontend/scripts/check-local-demo.mjs")], cwd=ROOT, env=env)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
