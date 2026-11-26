"""Load local configuration without overriding explicit process settings."""

import os
from pathlib import Path

from dotenv import dotenv_values


def load_local_environment(path: Path | None = None) -> None:
    # Never search the current directory: IDE and CLI starts use the same file.
    env_file = path if path is not None else Path(__file__).resolve().parents[1] / ".env"
    # Secrets containing dollar signs must retain their exact literal value.
    for key, value in dotenv_values(env_file, interpolate=False).items():
        if value is not None:
            os.environ.setdefault(key, value)
