from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
DEV_SECRET_KEY = "dev-only-change-me"
DEV_COACH_PASSWORD = "changeme"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ABGFC_", env_file=REPO_DIR / ".env", extra="ignore"
    )

    # "production" hides the API docs, forces Secure cookies and refuses the dev secrets.
    env: Literal["development", "production"] = "development"
    database_url: str = f"sqlite:///{REPO_DIR / 'data' / 'abgfc.db'}"
    media_dir: Path = REPO_DIR / "data" / "media"
    secret_key: str = Field(default=DEV_SECRET_KEY, min_length=16)
    session_max_age_seconds: int = 60 * 60 * 24 * 30
    cookie_secure: bool | None = None  # None = follow env (Secure in production)
    cors_origins: list[str] = ["http://localhost:3000"]
    # Used by `scripts/seed.py` to create the initial coach login.
    coach_username: str = "coach"
    coach_password: str = DEV_COACH_PASSWORD

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    @model_validator(mode="after")
    def _no_dev_secrets_in_production(self):
        if self.is_production:
            problems = []
            if self.secret_key == DEV_SECRET_KEY:
                problems.append("ABGFC_SECRET_KEY is the development default")
            if self.coach_password == DEV_COACH_PASSWORD:
                problems.append("ABGFC_COACH_PASSWORD is the development default")
            if problems:
                raise ValueError("Refusing to start in production: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
