"""Environment-backed settings shared by the API and migration commands."""

from dataclasses import dataclass
import os


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///./local-dev.db")
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str = _database_url()
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    company_id: str = os.getenv("COMPANY_ID", "qurlish")
    company_name: str = os.getenv("COMPANY_NAME", "Qurlish Construction")
    access_token_seconds: int = int(os.getenv("ACCESS_TOKEN_SECONDS", "900"))
    refresh_token_seconds: int = int(os.getenv("REFRESH_TOKEN_SECONDS", "1209600"))
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "0").lower() in {"1", "true", "yes"}


settings = Settings()
