"""Calling a match off.

Winter takes pitches out. A postponed match is not a deleted one: the fixture keeps the
date it was due, so the season still shows a match should have been played that day. The
league does not give it a new date - a replayed tie comes round as a new fixture - so
there is nothing here that moves a fixture.
"""

from fastapi.testclient import TestClient

from app.services.bootstrap import DemoSeason

API = "/api/v1"


def _scheduled(demo: DemoSeason) -> int:
    return next(f.id for f in demo.fixtures if f.status == "scheduled")


def test_postponing_keeps_the_date_it_should_have_been_played(
    auth_client: TestClient, demo: DemoSeason
):
    fx = _scheduled(demo)
    was = auth_client.get(f"{API}/fixtures/{fx}").json()["kickoff_at"]

    r = auth_client.post(f"{API}/fixtures/{fx}/postpone", json={"reason": "Waterlogged"})
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["status"] == "postponed"
    assert f["kickoff_at"] == was, "the date it was due is the record worth keeping"
    assert "Waterlogged" in f["notes"]


def test_a_played_match_cannot_be_postponed(auth_client: TestClient, demo: DemoSeason):
    played = next(f.id for f in demo.fixtures if f.status == "played")
    r = auth_client.post(f"{API}/fixtures/{played}/postpone", json={})
    assert r.status_code == 409 and "played" in r.json()["detail"]


def test_a_postponed_match_counts_for_nothing(auth_client: TestClient, demo: DemoSeason):
    """It is not a result. The record must not move."""
    ts = demo.team_season.id
    before = auth_client.get(f"{API}/team-seasons/{ts}/stats/summary").json()["overall"]
    auth_client.post(f"{API}/fixtures/{_scheduled(demo)}/postpone", json={"reason": "Frozen"})
    after = auth_client.get(f"{API}/team-seasons/{ts}/stats/summary").json()["overall"]
    assert before == after


def test_a_viewer_cannot_call_a_match_off(client: TestClient, demo: DemoSeason, db):
    from app.models import RoleScope, UserRole
    from tests.conftest import login_as, make_user

    make_user(db, "parent", (UserRole.VIEWER, RoleScope.TEAM, demo.team_season.club_team_id))
    db.commit()
    login_as(client, "parent")
    assert client.post(f"{API}/fixtures/{_scheduled(demo)}/postpone", json={}).status_code == 403
