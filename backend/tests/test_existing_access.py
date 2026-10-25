"""Every account shape that exists on the live site, proved to still work.

Written when parents moved from emailed links to passwords. The question that mattered
was not "does the new flow work" but "does anybody already signed up lose access", so
each test builds a row exactly as production holds it and signs in as that person.
"""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.ratelimit import signin_links, token_attempts
from app.core.security import hash_password
from app.models import PlayerGuardian, RoleScope, User, UserRole
from app.models import UserRoleAssignment as RoleRow
from app.services.bootstrap import DemoSeason
from tests.conftest import make_user

API = "/api/v1"


@pytest.fixture(autouse=True)
def _fresh_limits():
    signin_links.reset()
    token_attempts.reset()
    yield
    signin_links.reset()
    token_attempts.reset()


def _link(caplog) -> str:
    text = "\n".join(r.getMessage() for r in caplog.records if r.name == "abgfc.email")
    found = re.findall(r"https?://\S+/(?:invite|signin|reset)/([\w-]+)", text)
    assert found, f"no link in:\n{text}"
    return found[-1]


def _parent_row(db, demo: DemoSeason, email: str, *, password: str | None, child="Archie") -> User:
    """A parent exactly as the live table holds one: a cohort viewer role and a guardian
    link, with or without a password."""
    player = demo.players[child]
    user = User(
        username=email,
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password(password) if password else None,
    )
    user.roles.append(
        RoleRow(role=UserRole.VIEWER, scope_type=RoleScope.COHORT, scope_id=player.cohort_id)
    )
    user.guardian_of.append(PlayerGuardian(player_id=player.id))
    db.add(user)
    db.commit()
    return user


# --- coaches: nothing about them changed ------------------------------------------


def test_a_coach_signs_in_with_username_and_password(client: TestClient, db, demo: DemoSeason):
    """Rob, Stuart, the club admins. Username and password, no email on the row."""
    make_user(db, "rob", (UserRole.COACH, RoleScope.TEAM, demo.team_season.club_team_id))
    db.commit()
    r = client.post(f"{API}/auth/login", json={"username": "rob", "password": "secret"})
    assert r.status_code == 200
    assert r.json()["has_password"] is True and r.json()["email"] is None
    assert client.get(f"{API}/auth/me").status_code == 200


def test_a_coach_account_is_never_treated_as_a_parent(
    auth_client: TestClient, db, demo: DemoSeason
):
    """User 5 on the live site: a password and a cohort viewer role, but no children.
    It must not be deletable through the parents routes."""
    cohort = demo.team_season.club_team.cohort_id
    viewer = make_user(db, "louisedavies504", (UserRole.VIEWER, RoleScope.COHORT, cohort))
    db.commit()
    assert auth_client.delete(f"{API}/parents/{viewer.id}").status_code == 404
    assert auth_client.post(f"{API}/parents/{viewer.id}/close").status_code == 404
    # ...and they can still sign in
    r = TestClient(auth_client.app).post(
        f"{API}/auth/login", json={"username": "louisedavies504", "password": "secret"}
    )
    assert r.status_code == 200


# --- parents as the live table holds them today -----------------------------------


def test_parent_with_no_password_and_no_passkey_keeps_their_email_link(
    client: TestClient, db, demo: DemoSeason, caplog
):
    """Louise, Graham and Chris. The only way in they have is an emailed link, and it
    has to keep working now that the button says "Forgotten your password?"."""
    _parent_row(db, demo, "graham@example.com", password=None)
    with caplog.at_level("INFO", logger="abgfc.email"):
        r = client.post(f"{API}/auth/forgot-password", json={"email": "graham@example.com"})
    assert r.status_code == 204
    text = "\n".join(rec.getMessage() for rec in caplog.records if rec.name == "abgfc.email")
    assert "/signin/" in text and "/reset/" not in text  # the link they have always had

    assert client.post(f"{API}/auth/signin-link/{_link(caplog)}").status_code == 200
    me = client.get(f"{API}/auth/me").json()
    assert me["has_password"] is False
    assert sorted(t["team"]["name"] for t in me["teams"]) == ["Blacks", "Blues", "Reds", "Whites"]
    assert client.get(f"{API}/team-seasons/{demo.team_season.id}/squad").status_code == 200


def test_parent_with_a_passkey_and_no_password_still_gets_in_both_ways(
    client: TestClient, db, demo: DemoSeason, caplog
):
    """Charlotte. A passkey retired her email link under the old rule; now that email is
    only ever recovery, it works again - she must not be left with one brittle route."""
    user = _parent_row(db, demo, "charlotte@example.com", password=None, child="Max")
    from app.models import Passkey

    user.passkeys.append(Passkey(credential_id=b"cred-1", public_key=b"pub-1", sign_count=0))
    db.commit()

    with caplog.at_level("INFO", logger="abgfc.email"):
        assert (
            client.post(
                f"{API}/auth/forgot-password", json={"email": "charlotte@example.com"}
            ).status_code
            == 204
        )
    assert "/signin/" in "\n".join(
        r.getMessage() for r in caplog.records if r.name == "abgfc.email"
    )
    assert client.post(f"{API}/auth/signin-link/{_link(caplog)}").status_code == 200
    assert client.get(f"{API}/auth/me").json()["passkey_count"] == 1


def test_a_legacy_parent_can_set_a_password_without_losing_anything(
    client: TestClient, db, demo: DemoSeason, caplog
):
    user = _parent_row(db, demo, "chris@example.com", password=None)
    with caplog.at_level("INFO", logger="abgfc.email"):
        client.post(f"{API}/auth/forgot-password", json={"email": "chris@example.com"})
    client.post(f"{API}/auth/signin-link/{_link(caplog)}")

    assert (
        client.post(f"{API}/auth/set-password", json={"new_password": "their choice"}).status_code
        == 204
    )
    # The same account, the same child, now with a password
    db.expire_all()
    user = db.scalar(select(User).where(User.email == "chris@example.com"))
    assert len(user.guardian_of) == 1 and len(user.roles) == 1
    fresh = TestClient(client.app)
    assert (
        fresh.post(
            f"{API}/auth/login", json={"username": "chris@example.com", "password": "their choice"}
        ).status_code
        == 200
    )
    assert fresh.get(f"{API}/team-seasons/{demo.team_season.id}/squad").status_code == 200


def test_everyone_keeps_the_access_their_role_gives_them(
    client: TestClient, db, demo: DemoSeason, caplog
):
    """Read everything in the age group, write nothing - unchanged by the password work."""
    _parent_row(db, demo, "reader@example.com", password="a real password")
    r = client.post(
        f"{API}/auth/login", json={"username": "reader@example.com", "password": "a real password"}
    )
    assert r.status_code == 200
    ts = demo.team_season.id
    assert client.get(f"{API}/fixtures?team_season_id={ts}").status_code == 200
    assert client.get(f"{API}/team-seasons/{ts}/stats/summary").status_code == 200
    # ...and still cannot write or reach the coach-only report
    assert client.get(f"{API}/team-seasons/{ts}/reports/matchday.pdf").status_code == 403
    assert (
        client.post(
            f"{API}/invitations",
            json={"player_id": demo.players["Archie"].id, "email": "x@example.com"},
        ).status_code
        == 403
    )


def test_a_recent_session_survives_the_shorter_cookie(client: TestClient, db, demo: DemoSeason):
    """The cookie is 30 days now, down from 90 (NIST AAL1's overall timeout). A session
    inside the new window keeps working - nobody signed in this month is disturbed."""
    from app.config import get_settings
    from app.core.security import SESSION_COOKIE, create_session_token

    user = _parent_row(db, demo, "already.in@example.com", password=None)
    settings = get_settings()
    assert settings.session_max_age_seconds == 60 * 60 * 24 * 30
    client.cookies.set(
        SESSION_COOKIE, create_session_token(user.id, settings.secret_key, user.session_version)
    )
    assert client.get(f"{API}/auth/me").status_code == 200


def test_a_session_older_than_the_window_is_asked_again(client: TestClient, db, demo: DemoSeason):
    """Shortening the window does sign out anyone idle longer than it - that is the point
    of an overall timeout. They are asked to sign in, not locked out: a password, a
    passkey, or for the parents who predate passwords, the emailed link they still use."""
    from app.config import get_settings
    from app.core.security import SESSION_COOKIE, create_session_token

    user = _parent_row(db, demo, "long.ago@example.com", password=None)
    settings = get_settings()
    token = create_session_token(user.id, settings.secret_key, user.session_version)
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get(f"{API}/auth/me").status_code == 200

    # Stand in for "minted 31 days ago" by reading it against an already-elapsed window.
    # get_settings() builds a fresh Settings each call, so override the dependency.
    client.app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"session_max_age_seconds": -1}
    )
    assert client.get(f"{API}/auth/me").status_code == 401
    del client.app.dependency_overrides[get_settings]
    # And the way back in still exists
    r = client.post(f"{API}/auth/forgot-password", json={"email": "long.ago@example.com"})
    assert r.status_code == 204
