"""Parent access: invitations, passwordless sign-in, and leaving coaches alone."""

import re
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.ratelimit import signin_links, token_attempts
from app.core.security import create_session_token
from app.models import LoginToken, ParentAccessLog, PlayerGuardian, RoleScope, User, UserRole
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
    """The sign-in link only exists in the email; the console backend logs it. Take the
    *last* one: a test that invites and then asks for a sign-in link logs two."""
    text = "\n".join(r.getMessage() for r in caplog.records if r.name == "abgfc.email")
    found = re.findall(r"https?://\S+/(?:invite|signin|reset)/([\w-]+)", text)
    assert found, f"no link in the email log:\n{text}"
    return found[-1]


def _invite(client: TestClient, player_id: int, email: str | None = "mum@example.com"):
    """email=None is the WhatsApp flow: the coach sends the link, the parent gives
    their address when they accept."""
    body: dict = {"player_id": player_id}
    if email is not None:
        body["email"] = email
    return client.post(f"{API}/invitations", json=body)


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

    r = parent.post(
        f"{API}/auth/invitations/{token}/accept",
        json={"display_name": "Jo Smith", "password": "correct horse"},
    )
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["username"] == "mum@example.com" and me["display_name"] == "Jo Smith"
    assert me["email"] == "mum@example.com" and me["has_password"] is True
    assert me["roles"] == [{"role": "viewer", "scope_type": "cohort", "scope_id": archie.cohort_id}]
    # The multi-team role the age-group coach has: every team in the age group, read-only
    assert sorted(t["team"]["name"] for t in me["teams"]) == ["Blacks", "Blues", "Reds", "Whites"]
    assert {t["role"] for t in me["teams"]} == {"viewer"}

    # Signed in on the spot - no password was ever set
    assert parent.get(f"{API}/auth/me").status_code == 200
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
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


def test_one_parent_two_children_one_account(auth_client: TestClient, db, demo: DemoSeason, caplog):
    """A second child joins the same account - but only after the address is proved."""
    archie, max_ = demo.players["Archie"], demo.players["Max"]
    parent = _accept_as_parent(auth_client, archie.id)

    second = _invite(auth_client, max_.id).json()["link"].rsplit("/", 1)[1]
    with caplog.at_level("INFO", logger="abgfc.email"):
        r = parent.post(
            f"{API}/auth/invitations/{second}/accept",
            json={"display_name": "Jo", "password": "correct horse"},
        )
    # Not signed straight in: holding a link must not be enough to join an account
    assert r.status_code == 409 and "already has an account" in r.json()["detail"]
    users = db.scalars(select(User).where(User.email == "mum@example.com")).all()
    assert len(users) == 1
    assert [g.player_id for g in users[0].guardian_of] == [archie.id]

    # The emailed link is the proof, and following it adds the child
    r = parent.post(f"{API}/auth/signin-link/{_link_from_log(caplog)}")
    assert r.status_code == 200, r.text
    db.expire_all()
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    assert sorted(g.player_id for g in user.guardian_of) == sorted([archie.id, max_.id])
    assert len(user.roles) == 1  # one cohort role, not two
    assert "Max" in "\n".join(
        rec.getMessage() for rec in caplog.records if rec.name == "abgfc.email"
    )
    # And inviting the same pair again is refused outright
    assert _invite(auth_client, archie.id).status_code == 409


def test_an_invitation_cannot_take_over_a_coachs_login(
    auth_client: TestClient, db, demo: DemoSeason
):
    """Typing a coach's address must not hand the holder a login with write access."""
    coach = db.scalar(select(User).where(User.username == "coach"))
    coach.email = "boss@example.com"
    db.commit()
    # The WhatsApp flow, where the parent is the one supplying the address
    token = _invite(auth_client, demo.players["Archie"].id, None).json()["link"].rsplit("/", 1)[1]
    client = TestClient(auth_client.app)
    r = client.post(
        f"{API}/auth/invitations/{token}/accept",
        json={"display_name": "Chancer", "email": "boss@example.com", "password": "correct horse"},
    )
    assert r.status_code == 409 and "coach's login" in r.json()["detail"]
    assert client.get(f"{API}/auth/me").status_code == 401
    db.expire_all()
    assert db.scalar(select(User).where(User.username == "coach")).guardian_of == []

    # And where the coach named the address, the parent cannot substitute another
    token = (
        _invite(auth_client, demo.players["Max"].id, "mum@example.com")
        .json()["link"]
        .rsplit("/", 1)[1]
    )
    r = client.post(
        f"{API}/auth/invitations/{token}/accept",
        json={
            "display_name": "Jo",
            "email": "someone.else@example.com",
            "password": "correct horse",
        },
    )
    assert r.status_code == 200 and r.json()["email"] == "mum@example.com"


# --- the token rules ------------------------------------------------------------------


def test_a_link_works_once(auth_client: TestClient, demo: DemoSeason):
    token = _invite(auth_client, demo.players["Archie"].id).json()["link"].rsplit("/", 1)[1]
    parent = TestClient(auth_client.app)
    assert (
        parent.post(
            f"{API}/auth/invitations/{token}/accept",
            json={"display_name": "Jo", "password": "correct horse"},
        ).status_code
        == 200
    )
    r = parent.post(
        f"{API}/auth/invitations/{token}/accept",
        json={"display_name": "Jo", "password": "correct horse"},
    )
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
    parent.post(
        f"{API}/auth/invitations/{token}/accept",
        json={"display_name": "Jo", "password": "correct horse"},
    )
    return parent


def test_a_parent_with_a_long_email_can_sign_in(auth_client: TestClient, demo: DemoSeason):
    """`LoginRequest.username` was capped at 50 while a parent's username is their email,
    so anyone with a longer address was refused at the schema before authentication was
    even attempted."""
    long_email = "charlotte.fitzwilliam-harrington.parent@verylongdomainname.example.com"
    assert len(long_email) > 50
    _accept_as_parent(auth_client, demo.players["Archie"].id, long_email)

    fresh = TestClient(auth_client.app)
    r = fresh.post(f"{API}/auth/login", json={"username": long_email, "password": "correct horse"})
    assert r.status_code == 200, r.json()
    assert fresh.get(f"{API}/auth/me").json()["email"] == long_email


def test_password_guessing_is_throttled(auth_client: TestClient, demo: DemoSeason):
    """An unauthenticated password endpoint with no limit is an open invitation. Cyber
    Essentials allows no more than 10 guesses in 5 minutes."""
    client = TestClient(auth_client.app)
    attempt = {"username": "coach", "password": "wrong"}
    codes = [client.post(f"{API}/auth/login", json=attempt).status_code for _ in range(10)]
    assert codes == [401] * 10
    blocked = client.post(f"{API}/auth/login", json=attempt)
    assert blocked.status_code == 429
    # Even the right password now waits - the point is to slow the guesser down
    right = client.post(f"{API}/auth/login", json={"username": "coach", "password": "secret"})
    assert right.status_code == 429


def test_a_good_password_forgets_the_failures(auth_client: TestClient, demo: DemoSeason):
    """Otherwise a coach who fumbles it twice a week eventually locks themselves out."""
    client = TestClient(auth_client.app)
    for _ in range(9):
        client.post(f"{API}/auth/login", json={"username": "coach", "password": "wrong"})
    assert (
        client.post(
            f"{API}/auth/login", json={"username": "coach", "password": "secret"}
        ).status_code
        == 200
    )
    for _ in range(9):
        client.post(f"{API}/auth/login", json={"username": "coach", "password": "wrong"})
    assert (
        client.post(
            f"{API}/auth/login", json={"username": "coach", "password": "secret"}
        ).status_code
        == 200
    )


def test_forgotten_password(auth_client: TestClient, demo: DemoSeason, caplog):
    """A parent with a password gets a reset link - email used to recover, not to
    authenticate - and setting a new one signs them in."""
    _accept_as_parent(auth_client, demo.players["Archie"].id)
    client = TestClient(auth_client.app)
    with caplog.at_level("INFO", logger="abgfc.email"):
        r = client.post(f"{API}/auth/forgot-password", json={"email": "mum@example.com"})
    assert r.status_code == 204
    text = "\n".join(rec.getMessage() for rec in caplog.records if rec.name == "abgfc.email")
    assert "/reset/" in text and "Reset your ABGFC password" in text
    token = _link_from_log(caplog)

    assert client.get(f"{API}/auth/me").status_code == 401
    r = client.post(f"{API}/auth/reset-password/{token}", json={"new_password": "a new one"})
    assert r.status_code == 200, r.text
    assert client.get(f"{API}/auth/me").status_code == 200
    # The new password works and the old one doesn't
    fresh = TestClient(auth_client.app)
    assert (
        fresh.post(
            f"{API}/auth/login", json={"username": "mum@example.com", "password": "correct horse"}
        ).status_code
        == 401
    )
    assert (
        fresh.post(
            f"{API}/auth/login", json={"username": "mum@example.com", "password": "a new one"}
        ).status_code
        == 200
    )
    # Once only
    assert (
        client.post(
            f"{API}/auth/reset-password/{token}", json={"new_password": "a third one"}
        ).status_code
        == 404
    )


def test_a_parent_from_before_passwords_is_undisturbed(
    auth_client: TestClient, db, demo: DemoSeason, caplog
):
    """Graham and Chris joined before passwords existed. Their emailed sign-in links
    must keep working until they choose to set one."""
    parent = _accept_as_parent(auth_client, demo.players["Archie"].id)
    legacy = db.scalar(select(User).where(User.email == "mum@example.com"))
    legacy.password_hash = None  # as their rows actually are
    db.commit()

    client = TestClient(auth_client.app)
    with caplog.at_level("INFO", logger="abgfc.email"):
        assert (
            client.post(
                f"{API}/auth/forgot-password", json={"email": "mum@example.com"}
            ).status_code
            == 204
        )
    text = "\n".join(rec.getMessage() for rec in caplog.records if rec.name == "abgfc.email")
    assert "/signin/" in text  # the link they have always had, not a reset
    assert client.post(f"{API}/auth/signin-link/{_link_from_log(caplog)}").status_code == 200
    assert client.get(f"{API}/auth/me").json()["has_password"] is False

    # And they can set one whenever they like, with no current password to give
    assert (
        parent.post(f"{API}/auth/set-password", json={"new_password": "chosen later"}).status_code
        == 204
    )
    assert client.get(f"{API}/auth/me").json()["has_password"] is True
    fresh = TestClient(auth_client.app)
    assert (
        fresh.post(
            f"{API}/auth/login", json={"username": "mum@example.com", "password": "chosen later"}
        ).status_code
        == 200
    )


def test_signin_link_does_not_leak_who_has_an_account(auth_client: TestClient, caplog):
    client = TestClient(auth_client.app)
    with caplog.at_level("INFO", logger="abgfc.email"):
        r = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 204  # same answer as for a real address
    assert "nobody@example.com" not in "\n".join(
        rec.getMessage() for rec in caplog.records if rec.name == "abgfc.email"
    )


def test_signin_links_are_rate_limited(auth_client: TestClient, demo: DemoSeason):
    _accept_as_parent(auth_client, demo.players["Archie"].id)
    client = TestClient(auth_client.app)
    codes = [
        client.post(f"{API}/auth/forgot-password", json={"email": "mum@example.com"}).status_code
        for _ in range(7)
    ]
    assert codes[:5] == [204] * 5 and codes[5:] == [429, 429]


def test_a_coach_cannot_be_sent_a_signin_link(auth_client: TestClient, caplog):
    """Coaches have passwords; the link path must not become a way round that."""
    client = TestClient(auth_client.app)
    with caplog.at_level("INFO", logger="abgfc.email"):
        assert (
            client.post(
                f"{API}/auth/forgot-password", json={"email": "coach@example.com"}
            ).status_code
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

    body = auth_client.get(f"{API}/team-seasons/{demo.team_season.id}/parents").json()
    assert body["leavers"] == []
    by_name = {r["player"]["display_name"]: r for r in body["players"]}
    assert by_name["Archie"]["guardians"][0]["email"] == "mum@example.com"
    assert by_name["Archie"]["pending"] == []
    assert by_name["Max"]["pending"][0]["email"] == "max.dad@example.com"
    assert by_name["Max"]["guardians"] == []
    assert by_name["Teddy"]["guardians"] == [] and by_name["Teddy"]["pending"] == []

    # Coaches only - a parent can't see the list of parents
    parent = TestClient(auth_client.app)
    parent.post(f"{API}/auth/forgot-password", json={"email": "mum@example.com"})
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


# --- removing access ------------------------------------------------------------------


def test_a_child_leaving_surfaces_the_parent_to_remove(
    auth_client: TestClient, db, demo: DemoSeason
):
    """Access doesn't lapse by itself - the Parents tab says whose account to remove."""
    archie = demo.players["Archie"]
    parent = _accept_as_parent(auth_client, archie.id)
    url = f"{API}/team-seasons/{demo.team_season.id}/parents"
    assert auth_client.get(url).json()["leavers"] == []

    archie.left_date = datetime.now().date()
    db.commit()
    leavers = auth_client.get(url).json()["leavers"]
    assert len(leavers) == 1
    assert leavers[0]["email"] == "mum@example.com" and leavers[0]["children"] == ["Archie"]
    # Still in until somebody removes them
    assert parent.get(f"{API}/auth/me").status_code == 200

    user_id = leavers[0]["user_id"]
    assert auth_client.delete(f"{API}/parents/{user_id}").status_code == 204
    assert parent.get(f"{API}/auth/me").status_code == 401
    assert auth_client.get(url).json()["leavers"] == []
    # Gone, not dormant. (Re-inviting for Archie is refused because *he* has left, which
    # is a different rule - the address itself is free, see the next test.)
    assert db.get(User, user_id) is None


def test_a_second_child_still_playing_keeps_the_account(
    auth_client: TestClient, db, demo: DemoSeason, caplog
):
    archie, max_ = demo.players["Archie"], demo.players["Max"]
    parent = _accept_as_parent(auth_client, archie.id)
    second = _invite(auth_client, max_.id).json()["link"].rsplit("/", 1)[1]
    with caplog.at_level("INFO", logger="abgfc.email"):
        parent.post(
            f"{API}/auth/invitations/{second}/accept",
            json={"display_name": "Jo", "password": "correct horse"},
        )
        parent.post(f"{API}/auth/signin-link/{_link_from_log(caplog)}")

    archie.left_date = datetime.now().date()
    db.commit()
    url = f"{API}/team-seasons/{demo.team_season.id}/parents"
    assert auth_client.get(url).json()["leavers"] == []


def test_the_address_is_invitable_again_after_removal(
    auth_client: TestClient, db, demo: DemoSeason
):
    """There is no closed state to collide with: a removed parent is simply unknown."""
    archie = demo.players["Archie"]
    _accept_as_parent(auth_client, archie.id)
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    assert auth_client.delete(f"{API}/parents/{user.id}").status_code == 204

    again = _invite(auth_client, archie.id, "mum@example.com")
    assert again.status_code == 201
    token = again.json()["link"].rsplit("/", 1)[1]
    fresh = TestClient(auth_client.app)
    r = fresh.post(
        f"{API}/auth/invitations/{token}/accept",
        json={"display_name": "Mum", "password": "correct horse"},
    )
    assert r.status_code == 200
    assert fresh.get(f"{API}/auth/me").status_code == 200


def test_the_access_log_outlives_the_account(auth_client: TestClient, db, demo: DemoSeason):
    """The one thing a deleted account can't tell us - who could see this child - so it
    lives in its own append-only table with no FK to users."""
    archie = demo.players["Archie"]
    _accept_as_parent(auth_client, archie.id)
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    user_id = user.id

    def log():
        return db.scalars(
            select(ParentAccessLog)
            .where(ParentAccessLog.user_id == user_id)
            .order_by(ParentAccessLog.id)
        ).all()

    granted = log()
    assert [r.action for r in granted] == ["granted"]
    assert granted[0].player_id == archie.id
    assert granted[0].parent_email == "mum@example.com"

    assert auth_client.delete(f"{API}/parents/{user_id}").status_code == 204
    db.expire_all()
    assert db.get(User, user_id) is None  # the account is gone...
    rows = log()  # ...and the record is not
    assert [r.action for r in rows] == ["granted", "revoked"]
    # Readable without the account: the name and address are copied in, and the coach who
    # did it is on record.
    assert rows[1].parent_name == granted[0].parent_name  # copied in, not looked up
    assert rows[1].parent_email == "mum@example.com"
    assert rows[1].by_user_id == db.scalar(select(User.id).where(User.username == "coach"))


def test_removing_one_child_logs_only_that_child(auth_client: TestClient, db, demo: DemoSeason):
    archie, max_ = demo.players["Archie"], demo.players["Max"]
    _accept_as_parent(auth_client, archie.id)
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    db.add(PlayerGuardian(user_id=user.id, player_id=max_.id))
    db.commit()

    auth_client.delete(f"{API}/parents/{user.id}/children/{archie.id}")
    db.expire_all()
    revoked = db.scalars(select(ParentAccessLog).where(ParentAccessLog.action == "revoked")).all()
    assert [r.player_id for r in revoked] == [archie.id]


def test_sign_out_everywhere_keeps_the_account(auth_client: TestClient, db, demo: DemoSeason):
    """A phone left on a bus: kill the sessions, keep the access."""
    parent = _accept_as_parent(auth_client, demo.players["Archie"].id)
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    assert parent.get(f"{API}/auth/me").status_code == 200

    assert auth_client.post(f"{API}/parents/{user.id}/sign-out").status_code == 204
    assert parent.get(f"{API}/auth/me").status_code == 401
    db.refresh(user)
    assert user.is_active is True  # they can ask for a new link

    fresh = TestClient(auth_client.app)
    fresh.post(f"{API}/auth/forgot-password", json={"email": "mum@example.com"})
    assert db.scalar(select(User).where(User.email == "mum@example.com")).is_active


def test_only_a_coach_of_that_child_may_remove_the_account(
    client: TestClient, auth_client: TestClient, db, demo: DemoSeason
):
    _accept_as_parent(auth_client, demo.players["Archie"].id)
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    blues = demo.team_season.club_team_id
    make_user(db, "reds_coach", (UserRole.COACH, RoleScope.TEAM, blues + 1))
    make_user(db, "blues_viewer", (UserRole.VIEWER, RoleScope.TEAM, blues))
    db.commit()

    login_as(client, "reds_coach")
    assert client.delete(f"{API}/parents/{user.id}").status_code == 403
    login_as(client, "blues_viewer")
    assert client.delete(f"{API}/parents/{user.id}").status_code == 403
    # A coach account is not a parent and can't be removed through this route
    coach = db.scalar(select(User).where(User.username == "coach"))
    assert auth_client.delete(f"{API}/parents/{coach.id}").status_code == 404


def test_the_note_a_coach_sends_with_the_link(auth_client: TestClient, demo: DemoSeason):
    """Invitations usually travel as a WhatsApp direct message, so the app writes the
    note as well as the link - and says not to forward it."""
    from app.services.messages import invite_message

    created = _invite(auth_client, demo.players["Archie"].id).json()
    assert created["share_text"] == invite_message("Archie", created["link"], "Club admin")
    assert created["link"] in created["share_text"]
    assert "Archie's fixtures" in created["share_text"]
    assert "just for you" in created["share_text"]
    assert "Club admin has invited you" in created["share_text"]
    # No coach name on record still reads sensibly
    assert invite_message("Archie", "x", None).startswith("Your coach has invited you")


def test_invite_without_an_address_for_whatsapp(
    auth_client: TestClient, db, demo: DemoSeason, caplog
):
    """The coach has a phone number, not an email. They send the link themselves and
    the parent gives their address on the way in."""
    archie = demo.players["Archie"]
    with caplog.at_level("INFO", logger="abgfc.email"):
        r = _invite(auth_client, archie.id, None)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["email"] is None and created["emailed"] is False
    assert not [rec for rec in caplog.records if rec.name == "abgfc.email"]  # nothing sent
    assert created["link"] in created["share_text"]

    token = created["link"].rsplit("/", 1)[1]
    parent = TestClient(auth_client.app)
    # The landing page knows it must ask for an address
    assert parent.get(f"{API}/auth/invitations/{token}").json()["email"] is None
    # ...and refuses without one
    r = parent.post(
        f"{API}/auth/invitations/{token}/accept",
        json={"display_name": "Jo", "password": "correct horse"},
    )
    assert r.status_code == 422 and "email" in r.json()["detail"].lower()
    assert parent.get(f"{API}/auth/invitations/{token}").status_code == 200  # not spent

    r = parent.post(
        f"{API}/auth/invitations/{token}/accept",
        json={
            "display_name": "Jo Smith",
            "email": "Jo.Smith@Example.com ",
            "password": "correct horse",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "jo.smith@example.com"  # normalised
    assert parent.get(f"{API}/auth/me").status_code == 200
    user = db.scalar(select(User).where(User.email == "jo.smith@example.com"))
    assert [g.player_id for g in user.guardian_of] == [archie.id]
    # The password they chose works at the ordinary sign-in
    assert (
        parent.post(
            f"{API}/auth/login",
            json={"username": "jo.smith@example.com", "password": "correct horse"},
        ).status_code
        == 200
    )
    # Both parents of one child can be invited separately without clashing
    assert _invite(auth_client, archie.id, None).status_code == 201


# --- undoing access -------------------------------------------------------------------


def test_removing_one_childs_access(auth_client: TestClient, db, demo: DemoSeason):
    """One child of two: the account stays. The last one: it goes."""
    archie, max_ = demo.players["Archie"], demo.players["Max"]
    parent = _accept_as_parent(auth_client, archie.id)
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    db.add(PlayerGuardian(user_id=user.id, player_id=max_.id))
    db.commit()

    assert auth_client.delete(f"{API}/parents/{user.id}/children/{archie.id}").status_code == 204
    db.expire_all()
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    assert [g.player_id for g in user.guardian_of] == [max_.id]
    # Max is in the same age group, so they keep the role and stay signed in
    assert len(user.roles) == 1
    assert parent.get(f"{API}/auth/me").status_code == 200

    # Removing the last child removes the account: an account is exactly its links, and
    # one with none would be a ghost no coach could reach.
    user_id = user.id
    assert auth_client.delete(f"{API}/parents/{user_id}/children/{max_.id}").status_code == 204
    db.expire_all()
    assert db.scalar(select(User).where(User.email == "mum@example.com")) is None
    assert db.get(User, user_id) is None
    assert parent.get(f"{API}/auth/me").status_code == 401
    # ...and the coach can now invite that address afresh
    assert _invite(auth_client, archie.id).status_code == 201


def test_unlinking_is_scoped_like_everything_else(
    client: TestClient, auth_client: TestClient, db, demo: DemoSeason
):
    _accept_as_parent(auth_client, demo.players["Archie"].id)
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    make_user(db, "far_coach", (UserRole.COACH, RoleScope.TEAM, demo.team_season.club_team_id + 1))
    db.commit()
    login_as(client, "far_coach")
    r = client.delete(f"{API}/parents/{user.id}/children/{demo.players['Archie'].id}")
    assert r.status_code == 403
    # And a child they were never linked to is a 404, not a silent success
    login_as(client, "coach")
    r = auth_client.delete(f"{API}/parents/{user.id}/children/{demo.players['Teddy'].id}")
    assert r.status_code == 404


def test_deleting_a_parent_frees_the_address(auth_client: TestClient, db, demo: DemoSeason):
    """Closing keeps the row; deleting removes it, so they can be invited afresh."""
    archie = demo.players["Archie"]
    parent = _accept_as_parent(auth_client, archie.id)
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    user_id = user.id

    assert auth_client.delete(f"{API}/parents/{user_id}").status_code == 204
    assert parent.get(f"{API}/auth/me").status_code == 401
    db.expire_all()
    assert db.scalar(select(User).where(User.email == "mum@example.com")) is None
    # Everything hanging off it went too
    assert db.scalar(select(PlayerGuardian).where(PlayerGuardian.user_id == user_id)) is None

    # And the address is free: a brand new invitation, not "you already have an account"
    r = _invite(auth_client, archie.id)
    assert r.status_code == 201
    token = r.json()["link"].rsplit("/", 1)[1]
    fresh = TestClient(auth_client.app)
    r = fresh.post(
        f"{API}/auth/invitations/{token}/accept",
        json={"display_name": "Jo Again", "password": "correct horse"},
    )
    assert r.status_code == 200 and r.json()["display_name"] == "Jo Again"


def test_a_coachs_login_cannot_be_deleted_this_way(auth_client: TestClient, db):
    coach = db.scalar(select(User).where(User.username == "coach"))
    assert auth_client.delete(f"{API}/parents/{coach.id}").status_code == 404


def test_deleting_is_scoped_like_the_rest(client: TestClient, auth_client: TestClient, db, demo):
    _accept_as_parent(auth_client, demo.players["Archie"].id)
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    make_user(db, "distant", (UserRole.COACH, RoleScope.TEAM, demo.team_season.club_team_id + 1))
    db.commit()
    login_as(client, "distant")
    assert client.delete(f"{API}/parents/{user.id}").status_code == 403
