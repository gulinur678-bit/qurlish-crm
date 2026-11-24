"""Start only the migrated local demo; no seeding, password resets or migration."""

import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    database = ROOT / "demo_data/qurlish_demo.db"
    if database.is_symlink() or not database.is_file():
        raise SystemExit("Local demo database is missing or is a symlink.")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        if revision != ("20261124_v04",):
            raise SystemExit("Local demo migration must be verified first.")
    private = ROOT / "backups"
    if private.is_symlink():
        raise SystemExit("Private runtime directory cannot be a symlink.")
    private.mkdir(mode=0o700, exist_ok=True)
    os.chmod(private, 0o700)
    runtime = private / "local-demo-runtime.json"
    if runtime.is_symlink():
        raise SystemExit("Runtime configuration cannot be a symlink.")
    if not runtime.exists():
        fd = os.open(runtime, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump({"jwt_secret": secrets.token_urlsafe(48)}, output)
    os.chmod(runtime, 0o600)
    secret = json.loads(runtime.read_text()).get("jwt_secret")
    if not isinstance(secret, str) or len(secret) < 32:
        raise SystemExit("Invalid private runtime configuration; contents were not printed.")
    os.environ.update(DATABASE_URL="sqlite:///" + str(database), COMPANY_ID="qurlish", JWT_SECRET=secret, COOKIE_SECURE="0")
    import uvicorn
    print("Verified local demo database; backend listening on http://127.0.0.1:8000", flush=True)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
