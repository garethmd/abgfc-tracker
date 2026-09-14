"""Production mode must not expose docs or run on development secrets."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings


def test_development_defaults():
    s = Settings(_env_file=None)
    assert not s.is_production and not s.secure_cookies


def test_production_refuses_dev_secrets():
    with pytest.raises(ValueError, match="ABGFC_SECRET_KEY.*ABGFC_COACH_PASSWORD"):
        Settings(_env_file=None, env="production")
    with pytest.raises(ValueError, match="ABGFC_COACH_PASSWORD"):
        Settings(_env_file=None, env="production", secret_key="x" * 32)


def test_production_settings_ok_with_real_secrets():
    s = Settings(
        _env_file=None, env="production", secret_key="x" * 32, coach_password="s3cret-enough"
    )
    assert s.is_production and s.secure_cookies
    assert (
        Settings(
            _env_file=None,
            env="production",
            secret_key="x" * 32,
            coach_password="p" * 12,
            cookie_secure=False,
        ).secure_cookies
        is False
    )


def test_production_hides_docs(monkeypatch):
    from app.config import get_settings
    from app.main import create_app

    prod = Settings(_env_file=None, env="production", secret_key="x" * 32, coach_password="p" * 12)
    monkeypatch.setattr("app.main.get_settings", lambda: prod)
    with TestClient(create_app()) as c:
        assert c.get("/api/docs").status_code == 404
        assert c.get("/api/openapi.json").status_code == 404
        assert c.get("/api/health").status_code == 200
    monkeypatch.undo()  # back to development settings
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/api/docs").status_code == 200
