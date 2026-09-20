"""Live match entry: the same end state as PUT /result, written one tap at a time."""

from fastapi.testclient import TestClient

from app.models import FixtureStatus
from app.services.bootstrap import DemoSeason
from tests.conftest import login_as, make_user

API = "/api/v1"


def _scheduled(demo: DemoSeason):
    return next(f for f in demo.fixtures if f.match_number == 7)  # scheduled vs Fleet


def _board(client: TestClient, demo: DemoSeason):
    rows = client.get(f"{API}/team-seasons/{demo.team_season.id}/stats/leaderboard").json()["rows"]
    return {r["player"]["display_name"]: r for r in rows}


def test_live_flow_end_to_end(auth_client: TestClient, demo: DemoSeason):
    """Kick off -> goals -> undo -> goal against -> finish -> stats and Edit result agree."""
    fixture = _scheduled(demo)
    P = {name: p.id for name, p in demo.players.items()}
    squad = [P[n] for n in ["Archie", "Max", "Noah", "Jack", "Ayla", "Kayson", "Stanley", "Teddy"]]
    url = f"{API}/fixtures/{fixture.id}/live"

    r = auth_client.post(f"{url}/start", json={"player_ids": squad})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "live" and (d["our_score"], d["their_score"]) == (0, 0)
    assert len(d["appearances"]) == 8 and all(a["started"] for a in d["appearances"])

    # Viewers see the running score through the ordinary endpoint; stats ignore it.
    assert auth_client.get(f"{API}/fixtures/{fixture.id}").json()["status"] == "live"
    assert _board(auth_client, demo)["Archie"]["appearances"] == 6

    # Goal with an assist, then a goal that turns out to be the wrong scorer.
    d = auth_client.post(
        f"{url}/goals", json={"scorer_id": P["Teddy"], "assisted_by_id": P["Archie"], "sequence": 1}
    ).json()
    assert d["our_score"] == 1 and len(d["goals"]) == 1
    d = auth_client.post(f"{url}/goals", json={"scorer_id": P["Noah"], "sequence": 3}).json()
    assert d["our_score"] == 2
    wrong = d["goals"][1]["id"]
    d = auth_client.delete(f"{url}/goals/{wrong}").json()
    assert d["our_score"] == 1 and len(d["goals"]) == 1
    d = auth_client.post(f"{url}/goals", json={"scorer_id": P["Archie"], "sequence": 3}).json()
    assert d["our_score"] == 2

    # Retrying the same request (flaky signal) doesn't record it twice.
    d = auth_client.post(f"{url}/goals", json={"scorer_id": P["Archie"], "sequence": 3}).json()
    assert d["our_score"] == 2 and len(d["goals"]) == 2
    # ...but a different goal at a stale sequence is a conflict.
    r = auth_client.post(f"{url}/goals", json={"scorer_id": P["Max"], "sequence": 3})
    assert r.status_code == 409

    # Opposition goal: score only. Own goal: event + their score.
    d = auth_client.post(f"{url}/against").json()
    assert d["their_score"] == 1
    d = auth_client.post(
        f"{url}/goals", json={"event_type": "own_goal", "scorer_id": P["Jack"], "sequence": 5}
    ).json()
    assert d["their_score"] == 2
    d = auth_client.delete(f"{url}/against").json()
    assert d["their_score"] == 1
    r = auth_client.delete(f"{url}/against")  # only the own goal is left; nothing to remove
    assert r.status_code == 422
    d = auth_client.delete(f"{url}/goals/{d['goals'][-1]['id']}").json()
    assert d["their_score"] == 0 and len(d["goals"]) == 2

    # Late arrival; someone with a goal can't be dropped.
    r = auth_client.put(f"{url}/squad", json={"player_ids": squad + [P["William"]]})
    assert r.status_code == 200 and len(r.json()["appearances"]) == 9
    r = auth_client.put(f"{url}/squad", json={"player_ids": squad[1:]})
    assert r.status_code == 422 and "Archie" in r.json()["detail"]

    # The post-match screen must not write over a live match.
    r = auth_client.put(
        f"{API}/fixtures/{fixture.id}/result",
        json={"our_score": 0, "their_score": 0, "appearances": []},
    )
    assert r.status_code == 409

    d = auth_client.post(f"{url}/finish").json()
    assert d["status"] == "played" and (d["our_score"], d["their_score"]) == (2, 0)
    assert d["warnings"] == []
    assert [
        (g["scorer"]["display_name"], g["assisted_by"] and g["assisted_by"]["display_name"])
        for g in d["goals"]
    ] == [("Teddy", "Archie"), ("Archie", None)]

    board = _board(auth_client, demo)
    assert (
        board["Archie"]["goals"],
        board["Archie"]["assists"],
        board["Archie"]["appearances"],
    ) == (
        6,
        4,
        7,
    )
    assert (board["Teddy"]["goals"], board["Teddy"]["appearances"]) == (1, 3)
    summary = auth_client.get(f"{API}/team-seasons/{demo.team_season.id}/stats/summary").json()
    assert summary["overall"]["played"] == 7 and summary["overall"]["won"] == 3

    # Afterwards it's an ordinary played fixture: the awards step is the existing PUT.
    coaches = demo.award_types["coaches_potm"].id
    payload = {
        "our_score": 2,
        "their_score": 0,
        "appearances": [
            {"player_id": a["player"]["id"], "started": a["started"]} for a in d["appearances"]
        ],
        "goals": [
            {
                "event_type": g["event_type"],
                "scorer_id": g["scorer"]["id"],
                "assisted_by_id": g["assisted_by"] and g["assisted_by"]["id"],
            }
            for g in d["goals"]
        ],
        "awards": [{"award_type_id": coaches, "player_id": P["Teddy"]}],
    }
    r = auth_client.put(f"{API}/fixtures/{fixture.id}/result", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert [a["player"]["display_name"] for a in d["awards"]] == ["Teddy"]
    assert _board(auth_client, demo)["Archie"]["goals"] == 6

    # Live endpoints are closed once it's played.
    assert auth_client.post(f"{url}/against").status_code == 409
    assert auth_client.post(f"{url}/start", json={"player_ids": squad}).status_code == 409


def test_start_validation(auth_client: TestClient, demo: DemoSeason):
    fixture = _scheduled(demo)
    P = {name: p.id for name, p in demo.players.items()}
    url = f"{API}/fixtures/{fixture.id}/live"
    r = auth_client.post(f"{url}/start", json={"player_ids": [P["Archie"], P["Archie"]]})
    assert r.status_code == 422
    r = auth_client.post(f"{url}/start", json={"player_ids": [999_999]})
    assert r.status_code == 404
    # A played fixture can't be started.
    played = next(f for f in demo.fixtures if f.status == FixtureStatus.PLAYED)
    r = auth_client.post(
        f"{API}/fixtures/{played.id}/live/start", json={"player_ids": [P["Archie"]]}
    )
    assert r.status_code == 409
    # A scheduled fixture that somehow carries a result is never wiped by start.
    auth_client.put(
        f"{API}/fixtures/{fixture.id}/result",
        json={"our_score": 1, "their_score": 0, "appearances": [{"player_id": P["Archie"]}]},
    )
    auth_client.patch(f"{API}/fixtures/{fixture.id}", json={"status": "scheduled"})
    r = auth_client.post(f"{url}/start", json={"player_ids": [P["Max"]]})
    assert r.status_code == 409 and "Enter result" in r.json()["detail"]
    assert len(auth_client.get(f"{API}/fixtures/{fixture.id}").json()["appearances"]) == 1
    auth_client.patch(f"{API}/fixtures/{fixture.id}", json={"status": "played"})
    # And status can't be set to live through PATCH.
    r = auth_client.patch(f"{API}/fixtures/{fixture.id}", json={"status": "live"})
    assert r.status_code == 422


def test_goal_needs_a_player_who_is_on(auth_client: TestClient, demo: DemoSeason):
    fixture = _scheduled(demo)
    P = {name: p.id for name, p in demo.players.items()}
    url = f"{API}/fixtures/{fixture.id}/live"
    auth_client.post(f"{url}/start", json={"player_ids": [P["Archie"], P["Max"]]})
    r = auth_client.post(f"{url}/goals", json={"scorer_id": P["William"], "sequence": 1})
    assert r.status_code == 422 and "William" in r.json()["detail"]
    r = auth_client.post(
        f"{url}/goals",
        json={"scorer_id": P["Archie"], "assisted_by_id": P["Archie"], "sequence": 1},
    )
    assert r.status_code == 422
    r = auth_client.delete(f"{url}/goals/999999")
    assert r.status_code == 404


def test_abandon_returns_to_scheduled(auth_client: TestClient, demo: DemoSeason):
    fixture = _scheduled(demo)
    P = {name: p.id for name, p in demo.players.items()}
    url = f"{API}/fixtures/{fixture.id}/live"
    auth_client.post(f"{url}/start", json={"player_ids": [P["Archie"]]})
    auth_client.post(f"{url}/goals", json={"scorer_id": P["Archie"], "sequence": 1})
    assert auth_client.delete(url).status_code == 204
    d = auth_client.get(f"{API}/fixtures/{fixture.id}").json()
    assert d["status"] == "scheduled" and d["our_score"] is None
    assert d["appearances"] == [] and d["goals"] == []
    # Starting again works, and the old post-match flow is still open to it.
    assert auth_client.post(f"{url}/start", json={"player_ids": [P["Archie"]]}).status_code == 200
    auth_client.delete(url)
    r = auth_client.put(
        f"{API}/fixtures/{fixture.id}/result",
        json={"our_score": 1, "their_score": 0, "appearances": [{"player_id": P["Archie"]}]},
    )
    assert r.status_code == 200 and r.json()["status"] == "played"


def test_live_is_scoped(client: TestClient, db, demo: DemoSeason):
    """Viewers may watch the live score but can't write; other teams' coaches can't touch it."""
    from app.models import RoleScope, UserRole
    from app.services.bootstrap import seed_club_structure

    ts = seed_club_structure(db)
    make_user(db, "blues_coach", (UserRole.COACH, RoleScope.TEAM, ts["blues"].club_team_id))
    make_user(db, "reds_coach", (UserRole.COACH, RoleScope.TEAM, ts["reds"].club_team_id))
    make_user(db, "viewer", (UserRole.VIEWER, RoleScope.TEAM, ts["blues"].club_team_id))
    db.commit()
    fixture = _scheduled(demo)
    P = {name: p.id for name, p in demo.players.items()}
    url = f"{API}/fixtures/{fixture.id}/live"
    body = {"player_ids": [P["Archie"]]}

    login_as(client, "viewer")
    assert client.post(f"{url}/start", json=body).status_code == 403
    login_as(client, "reds_coach")
    assert client.post(f"{url}/start", json=body).status_code == 403

    login_as(client, "blues_coach")
    assert client.post(f"{url}/start", json=body).status_code == 200
    client.post(f"{url}/goals", json={"scorer_id": P["Archie"], "sequence": 1})

    login_as(client, "viewer")
    d = client.get(f"{API}/fixtures/{fixture.id}").json()
    assert d["status"] == "live" and d["our_score"] == 1
    for call in (
        lambda: client.post(f"{url}/goals", json={"scorer_id": P["Archie"], "sequence": 3}),
        lambda: client.post(f"{url}/against"),
        lambda: client.delete(f"{url}/against"),
        lambda: client.put(f"{url}/squad", json=body),
        lambda: client.post(f"{url}/finish"),
        lambda: client.delete(url),
    ):
        assert call().status_code == 403
    login_as(client, "reds_coach")
    assert client.get(f"{API}/fixtures/{fixture.id}").status_code == 403
    assert client.post(f"{url}/finish").status_code == 403
