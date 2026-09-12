"""Scoping: a team coach sees only their team; an age-group coach sees every team in the
cohort; a club admin sees everything. Children's data must not leak sideways."""

import pytest
from fastapi.testclient import TestClient

from app.models import RoleScope, UserRole
from app.services.bootstrap import DemoSeason, seed_club_structure
from tests.conftest import login_as, make_user

API = "/api/v1"


@pytest.fixture
def club(db, demo: DemoSeason):
    """Demo Blues season plus empty Blacks/Reds/Whites, and three users:
    blues_coach (team), stuart (cohort coach), reds_coach (team)."""
    ts = seed_club_structure(db)
    cohort_id = ts["blues"].club_team.cohort_id
    make_user(db, "blues_coach", (UserRole.COACH, RoleScope.TEAM, ts["blues"].club_team_id))
    make_user(db, "reds_coach", (UserRole.COACH, RoleScope.TEAM, ts["reds"].club_team_id))
    make_user(db, "stuart", (UserRole.COACH, RoleScope.COHORT, cohort_id))
    make_user(db, "viewer", (UserRole.VIEWER, RoleScope.TEAM, ts["blues"].club_team_id))
    db.commit()
    return ts


def test_team_coach_only_sees_their_team(client: TestClient, club, demo: DemoSeason):
    login_as(client, "blues_coach")
    me = client.get(f"{API}/auth/me").json()
    assert me["club_role"] is None
    assert [t["team"]["slug"] for t in me["teams"]] == ["blues"]
    assert me["teams"][0]["role"] == "coach"
    assert me["teams"][0]["current_team_season_id"] == demo.team_season.id
    assert [c["cohort"]["name"] for c in me["cohorts"]] == ["Born 2016/17"]

    assert [t["slug"] for t in client.get(f"{API}/club-teams").json()] == ["blues"]
    assert len(client.get(f"{API}/fixtures").json()) == 8  # all of them are Blues'

    # Reds' data is off limits - even knowing the ids.
    reds = club["reds"]
    assert client.get(f"{API}/team-seasons/{reds.id}").status_code == 403
    assert client.get(f"{API}/team-seasons/{reds.id}/squad").status_code == 403
    assert client.get(f"{API}/team-seasons/{reds.id}/stats/summary").status_code == 403
    assert client.get(f"{API}/fixtures?team_season_id={reds.id}").status_code == 403
    assert client.get(f"{API}/club-teams/{reds.club_team_id}").status_code == 403
    assert client.get(f"{API}/club-teams/by-slug/reds").status_code == 403
    r = client.post(
        f"{API}/fixtures",
        json={
            "team_season_id": reds.id,
            "competition_id": demo.competitions["League"].id,
            "opposition_team_id": demo.teams["Fleet Spurs"].id,
            "kickoff_at": "2026-11-01T10:00:00",
        },
    )
    assert r.status_code == 403

    # The cohort overview is not for team coaches, nor is user admin.
    assert (
        client.get(
            f"{API}/cohorts/{reds.club_team.cohort_id}/overview?season_id={demo.season.id}"
        ).status_code
        == 403
    )
    assert client.get(f"{API}/users").status_code == 403


def test_reds_coach_cannot_touch_blues_fixture(client: TestClient, club, demo: DemoSeason):
    login_as(client, "reds_coach")
    fx = demo.fixtures[0]
    assert client.get(f"{API}/fixtures/{fx.id}").status_code == 403
    assert client.delete(f"{API}/fixtures/{fx.id}").status_code == 403
    assert (
        client.put(
            f"{API}/fixtures/{fx.id}/result",
            json={"our_score": 9, "their_score": 0, "appearances": []},
        ).status_code
        == 403
    )
    # Blues' players are in the same cohort so their names are visible (for squad moves), but
    # not editable by a Reds coach.
    archie = demo.players["Archie"].id
    assert client.get(f"{API}/players/{archie}").status_code == 200
    assert client.patch(f"{API}/players/{archie}", json={"notes": "x"}).status_code == 403
    assert (
        client.get(f"{API}/players/{archie}/stats?team_season_id={demo.team_season.id}").status_code
        == 403
    )
    assert client.get(f"{API}/fixtures").json() == []


def test_viewer_can_read_but_not_write(client: TestClient, club, demo: DemoSeason):
    login_as(client, "viewer")
    assert client.get(f"{API}/team-seasons/{demo.team_season.id}/stats/summary").status_code == 200
    fx = demo.fixtures[6]
    body = {
        "our_score": 1,
        "their_score": 0,
        "appearances": [{"player_id": demo.players["Archie"].id}],
    }
    assert client.put(f"{API}/fixtures/{fx.id}/result", json=body).status_code == 403
    assert (
        client.put(
            f"{API}/team-seasons/{demo.team_season.id}/squad/{demo.players['Archie'].id}",
            json={"squad_number": 1},
        ).status_code
        == 403
    )


def test_cohort_coach_sees_every_team(client: TestClient, club, demo: DemoSeason):
    login_as(client, "stuart")
    me = client.get(f"{API}/auth/me").json()
    assert [t["team"]["slug"] for t in me["teams"]] == ["blues", "blacks", "reds", "whites"]
    assert all(t["role"] == "coach" for t in me["teams"])
    assert me["cohorts"][0]["role"] == "coach"

    reds = club["reds"]
    assert client.get(f"{API}/team-seasons/{reds.id}/squad").status_code == 200
    assert client.get(f"{API}/fixtures/{demo.fixtures[0].id}").status_code == 200

    # Overview: four teams side by side, players aggregated across the cohort.
    r = client.get(f"{API}/cohorts/{reds.club_team.cohort_id}/overview?season_id={demo.season.id}")
    assert r.status_code == 200, r.text
    ov = r.json()
    assert [t["team_name"] for t in ov["teams"]] == ["Blues", "Blacks", "Reds", "Whites"]
    assert ov["teams"][0]["overall"]["played"] == 6 and ov["teams"][0]["squad_size"] == 11
    assert ov["teams"][1]["overall"]["played"] == 0 and ov["teams"][1]["squad_size"] == 0
    archie = next(p for p in ov["players"] if p["player"]["display_name"] == "Archie")
    assert (archie["appearances"], archie["goals"], archie["teams"]) == (6, 5, ["Blues"])

    # Still no user admin: coach, not admin, at cohort scope.
    assert client.get(f"{API}/users").status_code == 403


def test_move_player_between_teams(client: TestClient, club, demo: DemoSeason):
    """Stuart moves Teddy from Blues to Reds mid-season; Blues keep his 2 appearances."""
    login_as(client, "stuart")
    teddy = demo.players["Teddy"].id
    r = client.post(
        f"{API}/players/{teddy}/move",
        json={
            "from_team_season_id": demo.team_season.id,
            "to_team_season_id": club["reds"].id,
            "left_at": "2026-10-15",
            "squad_number": 7,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["team_season_id"] == club["reds"].id and r.json()["squad_number"] == 7

    blues_squad = client.get(f"{API}/team-seasons/{demo.team_season.id}/squad").json()
    assert next(m for m in blues_squad if m["player"]["id"] == teddy)["left_at"] == "2026-10-15"
    board = client.get(f"{API}/team-seasons/{demo.team_season.id}/stats/leaderboard").json()
    assert next(r for r in board["rows"] if r["player"]["id"] == teddy)["appearances"] == 2
    reds_squad = client.get(f"{API}/team-seasons/{club['reds'].id}/squad").json()
    assert [m["player"]["display_name"] for m in reds_squad] == ["Teddy"]
    memberships = client.get(f"{API}/players/{teddy}/memberships").json()
    assert len(memberships) == 2

    # A team coach can't move players across teams.
    login_as(client, "blues_coach")
    r = client.post(
        f"{API}/players/{demo.players['Reece'].id}/move",
        json={"from_team_season_id": demo.team_season.id, "to_team_season_id": club["reds"].id},
    )
    assert r.status_code == 403


def test_cross_cohort_squad_is_rejected(auth_client: TestClient, club, demo: DemoSeason):
    """Players belong to an age group; a U12 team can't add a U10 child."""
    cohort = auth_client.post(
        f"{API}/cohorts", json={"name": "Born 2014/15", "birth_year_start": 2014}
    ).json()
    team = auth_client.post(
        f"{API}/club-teams", json={"cohort_id": cohort["id"], "name": "Blues"}
    ).json()
    assert team["slug"] == "blues-2"  # slug uniqueness is handled
    ts = auth_client.post(
        f"{API}/club-teams/{team['id']}/seasons", json={"season_id": demo.season.id}
    ).json()
    assert ts["age_group"] == "U12"
    r = auth_client.put(f"{API}/team-seasons/{ts['id']}/squad/{demo.players['Archie'].id}", json={})
    assert r.status_code == 422 and "different age group" in r.json()["detail"]


def test_user_admin_scoping(
    client: TestClient, auth_client: TestClient, club, demo: DemoSeason, db
):
    """Club admin creates a Blacks admin; that admin can add Blacks coaches but not Reds'."""
    blacks_id = club["blacks"].club_team_id
    reds_id = club["reds"].club_team_id
    r = auth_client.post(
        f"{API}/users",
        json={
            "username": "blacks_admin",
            "password": "secretsecret",
            "display_name": "Blacks lead",
            "roles": [{"role": "admin", "scope_type": "team", "scope_id": blacks_id}],
        },
    )
    assert r.status_code == 201, r.text
    assert auth_client.get(f"{API}/users").status_code == 200
    assert len(auth_client.get(f"{API}/users").json()) == 6  # coach + 4 fixtures users + new

    client.cookies.clear()
    r = client.post(
        f"{API}/auth/login", json={"username": "blacks_admin", "password": "secretsecret"}
    )
    assert r.status_code == 200
    # Can grant on Blacks...
    r = client.post(
        f"{API}/users",
        json={
            "username": "blacks_coach",
            "password": "secretsecret",
            "roles": [{"role": "coach", "scope_type": "team", "scope_id": blacks_id}],
        },
    )
    assert r.status_code == 201, r.text
    # ...not on Reds, nor at cohort/club scope.
    for i, roles in enumerate(
        (
            [{"role": "coach", "scope_type": "team", "scope_id": reds_id}],
            [
                {
                    "role": "coach",
                    "scope_type": "cohort",
                    "scope_id": club["reds"].club_team.cohort_id,
                }
            ],
            [{"role": "admin", "scope_type": "club"}],
        )
    ):
        r = client.post(
            f"{API}/users",
            json={"username": f"nope{i}", "password": "secretsecret", "roles": roles},
        )
        assert r.status_code == 403, roles
    # Sees only the users within their scope.
    assert {u["username"] for u in client.get(f"{API}/users").json()} == {
        "blacks_admin",
        "blacks_coach",
    }
    # Admin password reset then login with it.
    uid = next(
        u["id"] for u in client.get(f"{API}/users").json() if u["username"] == "blacks_coach"
    )
    assert (
        client.post(
            f"{API}/users/{uid}/password", json={"new_password": "newpassword1"}
        ).status_code
        == 204
    )
    client.cookies.clear()
    assert (
        client.post(
            f"{API}/auth/login", json={"username": "blacks_coach", "password": "newpassword1"}
        ).status_code
        == 200
    )
    # Self-service change password
    assert (
        client.post(
            f"{API}/auth/change-password",
            json={"current_password": "wrong", "new_password": "newpassword2"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{API}/auth/change-password",
            json={"current_password": "newpassword1", "new_password": "newpassword2"},
        ).status_code
        == 204
    )


def test_team_award_types_are_scoped(
    client: TestClient, auth_client: TestClient, club, demo: DemoSeason
):
    blues_id = demo.team_season.club_team_id
    login_as(client, "blues_coach")
    r = client.post(f"{API}/award-types", json={"name": "Most improved", "club_team_id": blues_id})
    assert r.status_code == 201, r.text
    assert r.json()["code"] == "blues_most_improved"
    # Club-wide needs club admin
    assert client.post(f"{API}/award-types", json={"name": "Golden boot"}).status_code == 403
    # Blues see three; Reds see two
    assert len(client.get(f"{API}/award-types?club_team_id={blues_id}").json()) == 3
    login_as(client, "reds_coach")
    assert (
        len(client.get(f"{API}/award-types?club_team_id={club['reds'].club_team_id}").json()) == 2
    )
    # And the leaderboard grows a column for Blues only
    login_as(client, "blues_coach")
    board = client.get(f"{API}/team-seasons/{demo.team_season.id}/stats/leaderboard").json()
    assert [a["award_type_code"] for a in board["award_types"]] == [
        "coaches_potm",
        "parents_potm",
        "blues_most_improved",
    ]
