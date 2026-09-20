"""Opposition teams as first-class: record and fixture history against them, scoped."""

from fastapi.testclient import TestClient

from app.models import RoleScope, UserRole
from app.services.bootstrap import DemoSeason, seed_club_structure
from tests.conftest import login_as, make_user

API = "/api/v1"


def test_head_to_head_record_and_history(auth_client: TestClient, demo: DemoSeason):
    farnborough = demo.teams["Farnborough Town Youth"].id  # W 3-1 (m1), L 1-3 (m6)
    r = auth_client.get(f"{API}/teams/{farnborough}/head-to-head")
    assert r.status_code == 200, r.text
    h = r.json()
    assert h["team"]["name"] == "Farnborough Town Youth"
    assert h["record"] == {
        "played": 2,
        "won": 1,
        "drawn": 0,
        "lost": 1,
        "goals_for": 4,
        "goals_against": 4,
        "goal_difference": 0,
        "win_pct": 50.0,
    }
    assert h["form"] == ["W", "L"]
    assert [
        (f["match_number"], f["result"], f["our_score"], f["their_score"]) for f in h["played"]
    ] == [(6, "L", 1, 3), (1, "W", 3, 1)]
    assert (
        h["played"][0]["club_team_name"] == "Blues" and h["played"][0]["season_name"] == "2026/27"
    )
    assert h["upcoming"] == [] and h["other"] == []

    hook = demo.teams["Hook Juniors"].id  # W 5-0 (m4) + postponed cup (m8)
    h = auth_client.get(f"{API}/teams/{hook}/head-to-head").json()
    assert h["record"]["played"] == 1 and [f["status"] for f in h["other"]] == ["postponed"]

    fleet = demo.teams["Fleet Spurs"].id  # D 2-2 (m2) + scheduled (m7)
    h = auth_client.get(f"{API}/teams/{fleet}/head-to-head").json()
    assert h["record"]["drawn"] == 1 and [f["match_number"] for f in h["upcoming"]] == [7]


def test_head_to_head_is_scoped(client: TestClient, db, demo: DemoSeason):
    ts = seed_club_structure(db)
    make_user(db, "reds", (UserRole.COACH, RoleScope.TEAM, ts["reds"].club_team_id))
    make_user(db, "blues", (UserRole.VIEWER, RoleScope.TEAM, demo.team_season.club_team_id))
    db.commit()
    farnborough = demo.teams["Farnborough Town Youth"].id
    # A Reds coach sees the opponent but none of Blues' fixtures against them
    login_as(client, "reds")
    h = client.get(f"{API}/teams/{farnborough}/head-to-head").json()
    assert h["record"]["played"] == 0 and h["played"] == []
    assert (
        client.get(
            f"{API}/teams/{farnborough}/head-to-head?club_team_id={demo.team_season.club_team_id}"
        ).status_code
        == 403
    )
    # A Blues viewer sees Blues' history
    login_as(client, "blues")
    h = client.get(
        f"{API}/teams/{farnborough}/head-to-head?club_team_id={demo.team_season.club_team_id}"
    ).json()
    assert h["record"]["played"] == 2
    assert client.get(f"{API}/teams/999/head-to-head").status_code == 404
