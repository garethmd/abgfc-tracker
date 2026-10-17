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
    # Long on purpose: this is read-only club information on a parent's own phone, and
    # a sign-in they have to repeat is a sign-in they'll ask a coach for help with.
    session_max_age_seconds: int = 60 * 60 * 24 * 90
    cookie_secure: bool | None = None  # None = follow env (Secure in production)
    cors_origins: list[str] = ["http://localhost:3000"]
    # Used by `scripts/seed.py` to create the initial coach login.
    coach_username: str = "coach"
    coach_password: str = DEV_COACH_PASSWORD

    # Where the app is reached from outside - used to build emailed links.
    public_base_url: str = "http://localhost:3000"
    # "console" logs the email instead of sending it (development and tests).
    email_backend: Literal["console", "resend", "mailgun"] = "console"
    email_from: str = "ABGFC Blues <noreply@abgfc.neuralaspect.com>"
    # The sending domain has no MX, so replies to the From address bounce: point this
    # at a mailbox somebody reads.
    email_reply_to: str = ""
    email_api_key: str = ""
    mailgun_domain: str = "abgfc.neuralaspect.com"
    # WebAuthn: the relying-party id is the registrable domain, and the browser will
    # refuse any credential whose origin doesn't match - that is the phishing resistance.
    # Derived from public_base_url unless set explicitly (localhost in development).
    webauthn_rp_id: str = ""
    webauthn_rp_name: str = "ABGFC"
    webauthn_challenge_ttl_seconds: int = 300
    invite_expiry_hours: int = 24 * 14
    signin_link_expiry_minutes: int = 15
    reset_link_expiry_minutes: int = 30

    @property
    def rp_id(self) -> str:
        """Host only - no scheme, no port. localhost is a valid RP id for development."""
        if self.webauthn_rp_id:
            return self.webauthn_rp_id
        host = self.public_base_url.split("//", 1)[-1].split("/", 1)[0]
        return host.split(":", 1)[0]

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
            if self.email_backend != "console" and not self.email_api_key:
                problems.append(
                    f"ABGFC_EMAIL_BACKEND={self.email_backend} but ABGFC_EMAIL_API_KEY is empty"
                )
            if problems:
                raise ValueError("Refusing to start in production: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
