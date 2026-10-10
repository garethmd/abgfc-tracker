"""Parent access: invitations, passwordless sign-in, and leaving coaches alone."""

import re
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.ratelimit import signin_links, token_attempts
from app.core.security import create_session_token
from app.models import LoginToken, PlayerGuardian, RoleScope, User, UserRole
from app.services.bootstrap import DemoSeason
from tests.conftest import login_as, make_user

API = "/api/v1"


@pytest.fixture(autouse=True)
def _fresh_limits():
    signin_links.reset()
    token_attempts.reset()
    yield
    signin_links.reset()
    token_attempts.reset()


def _link_from_log(caplog) -> str:
    """The sign-in link only exists in the email; the console backend logs it."""
    text = "\n".join(r.getMessage() for r in caplog.records if r.name == "abgfc.email")
    m = re.search(r"https?://\S+/(?:invite|signin)/([\w-]+)", text)
    assert m, f"no link in the email log:\n{text}"
    return m.group(1)


def _invite(client: TestClient, player_id: int, email: str = "mum@example.com"):
    return client.post(f"{API}/invitations", json={"email": email, "player_id": player_id})


# --- the happy path -------------------------------------------------------------------


def test_invite_accept_and_see_the_club(auth_client: TestClient, db, demo: DemoSeason, caplog):
    archie = demo.players["Archie"]
    with caplog.at_level("INFO", logger="abgfc.email"):
        r = _invite(auth_client, archie.id)
    assert r.status_code == 201, r.text
    invite = r.json()
    assert invite["email"] == "mum@example.com"
    assert invite["player"]["display_name"] == "Archie"
    assert invite["emailed"] is True  # console backend "sent" it
    token = invite["link"].rsplit("/", 1)[1]
    assert _link_from_log(caplog) == token  # the same link went in the email

    # The landing page describes the invitation without spending it
    parent = TestClient(auth_client.app)
    r = parent.get(f"{API}/auth/invitations/{token}")
    assert r.status_code == 200, r.text
    assert r.json()["player_name"] == "Archie"
    assert r.json()["team_names"] == ["Blues"]
    assert r.json()["invited_by"] == "Club admin"
    assert parent.get(f"{API}/auth/invitations/{token}").status_code == 200  # still live

    r = parent.post(f"{API}/auth/invitations/{token}/accept", json={"display_name": "Jo Smith"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["username"] == "mum@example.com" and me["display_name"] == "Jo Smith"
    assert me["email"] == "mum@example.com" and me["has_password"] is False
    assert me["roles"] == [{"role": "viewer", "scope_type": "cohort", "scope_id": archie.cohort_id}]
    # The multi-team role the age-group coach has: every team in the age group, read-only
    assert sorted(t["team"]["name"] for t in me["teams"]) == ["Blacks", "Blues", "Reds", "Whites"]
    assert {t["role"] for t in me["teams"]} == {"viewer"}

    # Signed in on the spot - no password was ever set
    assert parent.get(f"{API}/auth/me").status_code == 200
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    assert user.password_hash is None
    assert [g.player_id for g in user.guardian_of] == [archie.id]

    # A viewer reads but cannot write, and the coach-only reports stay shut
    ts = demo.team_season.id
    assert parent.get(f"{API}/team-seasons/{ts}/squad").status_code == 200
    assert parent.get(f"{API}/fixtures?team_season_id={ts}").status_code == 200
    assert parent.get(f"{API}/team-seasons/{ts}/reports/matchday.pdf").status_code == 403
    assert _invite(parent, archie.id, "dad@example.com").status_code == 403
    r = parent.post(
        f"{API}/fixtures",
        json={
            "team_season_id": ts,
            "competition_id": next(iter(demo.competitions.values())).id,
            "opposition_team_id": demo.teams["Fleet Spurs"].id,
            "kickoff_at": "2026-11-07T10:00:00",
        },
    )
    assert r.status_code == 403


def test_one_parent_two_children_one_account(auth_client: TestClient, db, demo: DemoSeason):
    archie, max_ = demo.players["Archie"], demo.players["Max"]
    first = _invite(auth_client, archie.id).json()
    parent = TestClient(auth_client.app)
    parent.post(
        f"{API}/auth/invitations/{first['link'].rsplit('/', 1)[1]}",
        json={"display_name": "Jo"},
    )
    parent.post(
        f"{API}/auth/invitations/{first['link'].rsplit('/', 1)[1]}/accept",
        json={"display_name": "Jo"},
    )
    second = _invite(auth_client, max_.id).json()
    r = parent.post(
        f"{API}/auth/invitations/{second['link'].rsplit('/', 1)[1]}/accept",
        json={"display_name": "Jo"},
    )
    assert r.status_code == 200
    users = db.scalars(select(User).where(User.email == "mum@example.com")).all()
    assert len(users) == 1
    assert sorted(g.player_id for g in users[0].guardian_of) == sorted([archie.id, max_.id])
    # One role row, not two
    assert len(users[0].roles) == 1
    # And inviting the same pair again is refused
    assert _invite(auth_client, archie.id).status_code == 409


# --- the token rules ------------------------------------------------------------------


def test_a_link_works_once(auth_client: TestClient, demo: DemoSeason):
    token = _invite(auth_client, demo.players["Archie"].id).json()["link"].rsplit("/", 1)[1]
    parent = TestClient(auth_client.app)
    assert (
        parent.post(
            f"{API}/auth/invitations/{token}/accept", json={"display_name": "Jo"}
        ).status_code
        == 200
    )
    r = parent.post(f"{API}/auth/invitations/{token}/accept", json={"display_name": "Jo"})
    assert r.status_code == 404
    assert parent.get(f"{API}/auth/invitations/{token}").status_code == 404


def test_expired_revoked_and_unknown_links(auth_client: TestClient, db, demo: DemoSeason):
    client = TestClient(auth_client.app)
    assert client.get(f"{API}/auth/invitations/nonsense").status_code == 404

    created = _invite(auth_client, demo.players["Archie"].id).json()
    token = db.scalar(select(LoginToken).where(LoginToken.id == created["id"]))
    token.expires_at = datetime.now() - timedelta(minutes=1)
    db.commit()
    assert (
        client.get(f"{API}/auth/invitations/{created['link'].rsplit('/', 1)[1]}").status_code == 404
    )

    second = _invite(auth_client, demo.players["Max"].id).json()
    assert auth_client.delete(f"{API}/invitations/{second['id']}").status_code == 204
    assert (
        client.get(f"{API}/auth/invitations/{second['link'].rsplit('/', 1)[1]}").status_code == 404
    )
    assert auth_client.delete(f"{API}/invitations/{second['id']}").status_code == 404


def test_reinviting_replaces_the_earlier_link(auth_client: TestClient, demo: DemoSeason):
    archie = demo.players["Archie"].id
    first = _invite(auth_client, archie).json()["link"].rsplit("/", 1)[1]
    second = _invite(auth_client, archie).json()["link"].rsplit("/", 1)[1]
    client = TestClient(auth_client.app)
    assert client.get(f"{API}/auth/invitations/{first}").status_code == 404
    assert client.get(f"{API}/auth/invitations/{second}").status_code == 200


# --- signing in again -----------------------------------------------------------------


def _accept_as_parent(auth_client: TestClient, player_id: int, email="mum@example.com"):
    token = _invite(auth_client, player_id, email).json()["link"].rsplit("/", 1)[1]
    parent = TestClient(auth_client.app)
    parent.post(f"{API}/auth/invitations/{token}/accept", json={"display_name": "Jo"})
    return parent


def test_sign_in_link(auth_client: TestClient, demo: DemoSeason, caplog):
    _accept_as_parent(auth_client, demo.players["Archie"].id)
    client = TestClient(auth_client.app)
    with caplog.at_level("INFO", logger="abgfc.email"):
        r = client.post(f"{API}/auth/signin-link", json={"email": "mum@example.com"})
    assert r.status_code == 204
    token = _link_from_log(caplog)

    assert client.get(f"{API}/auth/me").status_code == 401
    r = client.post(f"{API}/auth/signin-link/{token}")
    assert r.status_code == 200 and r.json()["email"] == "mum@example.com"
    assert client.get(f"{API}/auth/me").status_code == 200
    # Once only
    assert client.post(f"{API}/auth/signin-link/{token}").status_code == 404


def test_signin_link_does_not_leak_who_has_an_account(auth_client: TestClient, caplog):
    client = TestClient(auth_client.app)
    with caplog.at_level("INFO", logger="abgfc.email"):
        r = client.post(f"{API}/auth/signin-link", json={"email": "nobody@example.com"})
    assert r.status_code == 204  # same answer as for a real address
    assert "nobody@example.com" not in "\n".join(
        rec.getMessage() for rec in caplog.records if rec.name == "abgfc.email"
    )


def test_signin_links_are_rate_limited(auth_client: TestClient, demo: DemoSeason):
    _accept_as_parent(auth_client, demo.players["Archie"].id)
    client = TestClient(auth_client.app)
    codes = [
        client.post(f"{API}/auth/signin-link", json={"email": "mum@example.com"}).status_code
        for _ in range(7)
    ]
    assert codes[:5] == [204] * 5 and codes[5:] == [429, 429]


def test_a_coach_cannot_be_sent_a_signin_link(auth_client: TestClient, caplog):
    """Coaches have passwords; the link path must not become a way round that."""
    client = TestClient(auth_client.app)
    with caplog.at_level("INFO", logger="abgfc.email"):
        assert (
            client.post(f"{API}/auth/signin-link", json={"email": "coach@example.com"}).status_code
            == 204
        )
    assert not [r for r in caplog.records if r.name == "abgfc.email"]


# --- coaches are untouched ------------------------------------------------------------


def test_existing_password_login_still_works(auth_client: TestClient):
    auth_client.cookies.clear()
    r = auth_client.post(f"{API}/auth/login", json={"username": "coach", "password": "secret"})
    assert r.status_code == 200 and r.json()["username"] == "coach"


def test_a_parent_cannot_sign_in_with_a_password(auth_client: TestClient, demo: DemoSeason):
    _accept_as_parent(auth_client, demo.players["Archie"].id)
    client = TestClient(auth_client.app)
    for password in ("", "secret", "x"):
        r = client.post(
            f"{API}/auth/login", json={"username": "mum@example.com", "password": password or "x"}
        )
        assert r.status_code == 401


def test_cookies_issued_before_session_versions_still_work(auth_client: TestClient, db):
    """Deploying this must not sign every coach out."""
    from app.config import get_settings
    from app.core.security import SESSION_COOKIE, _serializer

    user = db.scalar(select(User).where(User.username == "coach"))
    legacy = _serializer(get_settings().secret_key).dumps({"uid": user.id})  # no "sv"
    client = TestClient(auth_client.app)
    client.cookies.set(SESSION_COOKIE, legacy)
    assert client.get(f"{API}/auth/me").status_code == 200


def test_bumping_the_session_version_signs_a_device_out(auth_client: TestClient, db):
    from app.config import get_settings
    from app.core.security import SESSION_COOKIE

    user = db.scalar(select(User).where(User.username == "coach"))
    client = TestClient(auth_client.app)
    client.cookies.set(
        SESSION_COOKIE,
        create_session_token(user.id, get_settings().secret_key, user.session_version),
    )
    assert client.get(f"{API}/auth/me").status_code == 200
    user.session_version += 1
    db.commit()
    assert client.get(f"{API}/auth/me").status_code == 401


# --- who may invite -------------------------------------------------------------------


def test_only_a_coach_of_that_child_may_invite(client: TestClient, db, demo: DemoSeason):
    blues = demo.team_season.club_team_id
    cohort = demo.team_season.club_team.cohort_id
    make_user(db, "blues_coach", (UserRole.COACH, RoleScope.TEAM, blues))
    make_user(db, "blues_viewer", (UserRole.VIEWER, RoleScope.TEAM, blues))
    make_user(db, "age_group_coach", (UserRole.COACH, RoleScope.COHORT, cohort))
    # Another team in the same age group - Archie is not in their squad
    make_user(db, "reds_coach", (UserRole.COACH, RoleScope.TEAM, blues + 1))
    db.commit()
    archie = demo.players["Archie"].id

    login_as(client, "blues_viewer")
    assert _invite(client, archie, "a@example.com").status_code == 403
    login_as(client, "reds_coach")  # another team in the same age group, not Archie's
    assert _invite(client, archie, "b@example.com").status_code == 403
    login_as(client, "age_group_coach")
    assert _invite(client, archie, "c@example.com").status_code == 201
    login_as(client, "blues_coach")
    assert _invite(client, archie, "d@example.com").status_code == 201


def test_cannot_invite_for_a_child_who_has_left(auth_client: TestClient, db, demo: DemoSeason):
    archie = demo.players["Archie"]
    archie.left_date = datetime.now().date()
    db.commit()
    r = _invite(auth_client, archie.id)
    assert r.status_code == 422 and "left" in r.json()["detail"]


# --- the Parents tab ------------------------------------------------------------------


def test_parents_tab_lists_access_per_child(auth_client: TestClient, db, demo: DemoSeason):
    archie = demo.players["Archie"].id
    _accept_as_parent(auth_client, archie)
    _invite(auth_client, demo.players["Max"].id, "max.dad@example.com")

    rows = auth_client.get(f"{API}/team-seasons/{demo.team_season.id}/parents").json()
    by_name = {r["player"]["display_name"]: r for r in rows}
    assert by_name["Archie"]["guardians"][0]["email"] == "mum@example.com"
    assert by_name["Archie"]["guardians"][0]["is_active"] is True
    assert by_name["Archie"]["pending"] == []
    assert by_name["Max"]["pending"][0]["email"] == "max.dad@example.com"
    assert by_name["Max"]["guardians"] == []
    assert by_name["Teddy"]["guardians"] == [] and by_name["Teddy"]["pending"] == []

    # Coaches only - a parent can't see the list of parents
    parent = TestClient(auth_client.app)
    parent.post(f"{API}/auth/signin-link", json={"email": "mum@example.com"})
    assert parent.get(f"{API}/team-seasons/{demo.team_season.id}/parents").status_code == 401


def test_closing_an_account_locks_the_parent_out(auth_client: TestClient, db, demo: DemoSeason):
    parent = _accept_as_parent(auth_client, demo.players["Archie"].id)
    assert parent.get(f"{API}/auth/me").status_code == 200
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    user.is_active = False
    db.commit()
    assert parent.get(f"{API}/auth/me").status_code == 401
    # And the guardian link is still there to say why they had access
    assert db.scalar(select(PlayerGuardian).where(PlayerGuardian.user_id == user.id)) is not None
