from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ABGFC_", env_file=REPO_DIR / ".env", extra="ignore"
    )

    database_url: str = f"sqlite:///{REPO_DIR / 'data' / 'abgfc.db'}"
    media_dir: Path = REPO_DIR / "data" / "media"
    secret_key: str = Field(default="dev-only-change-me", min_length=16)
    session_max_age_seconds: int = 60 * 60 * 24 * 30
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]
    # Used by `scripts/seed.py` to create the initial coach login.
    coach_username: str = "coach"
    coach_password: str = "changeme"


@lru_cache
def get_settings() -> Settings:
    return Settings()
