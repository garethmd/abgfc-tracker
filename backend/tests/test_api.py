from fastapi.testclient import TestClient

from app.services.bootstrap import DemoSeason

API = "/api/v1"


def test_everything_requires_login(client: TestClient):
    for path in [
        f"{API}/seasons",
        f"{API}/players",
        f"{API}/fixtures",
        f"{API}/auth/me",
        f"{API}/club-teams",
        f"{API}/users",
    ]:
        assert client.get(path).status_code == 401, path


def test_login_bad_password(client: TestClient, db):
    from app.services.bootstrap import seed_user

    seed_user(db, "coach", "secret")
    db.commit()
    r = client.post(f"{API}/auth/login", json={"username": "coach", "password": "nope"})
    assert r.status_code == 401


def test_login_logout(auth_client: TestClient):
    me = auth_client.get(f"{API}/auth/me").json()
    assert me["username"] == "coach" and me["club_role"] == "admin"
    assert auth_client.post(f"{API}/auth/logout").status_code == 204
    assert auth_client.get(f"{API}/auth/me").status_code == 401


def test_team_season_start_and_roll_over(auth_client: TestClient, demo: DemoSeason):
    team_id = demo.team_season.club_team_id
    seasons = auth_client.get(f"{API}/club-teams/{team_id}/seasons").json()
    assert [s["season"]["name"] for s in seasons] == ["2026/27"]
    assert seasons[0]["is_current"] and seasons[0]["age_group"] == "U10"

    # Roll into next season, copying the squad forward; age group is derived.
    r = auth_client.post(
        f"{API}/club-teams/{team_id}/seasons",
        json={
            "season_name": "2027/28",
            "copy_squad_from_team_season_id": demo.team_season.id,
            "match_minutes": 60,
        },
    )
    assert r.status_code == 201, r.text
    nxt = r.json()
    assert nxt["season"]["name"] == "2027/28" and nxt["age_group"] == "U11" and nxt["is_current"]
    squad = auth_client.get(f"{API}/team-seasons/{nxt['id']}/squad").json()
    assert len(squad) == 11 and {m["squad_number"] for m in squad} == set(range(1, 12))
    assert (
        auth_client.get(f"{API}/team-seasons/{demo.team_season.id}").json()["is_current"] is False
    )

    # Same season twice is a conflict; the club-wide season row was created once.
    assert (
        auth_client.post(
            f"{API}/club-teams/{team_id}/seasons", json={"season_name": "2027/28"}
        ).status_code
        == 409
    )
    assert [s["name"] for s in auth_client.get(f"{API}/seasons").json()] == ["2027/28", "2026/27"]

    # Fresh season stats are all zeros but the squad is listed.
    board = auth_client.get(f"{API}/team-seasons/{nxt['id']}/stats/leaderboard").json()
    assert len(board["rows"]) == 11 and all(r["appearances"] == 0 for r in board["rows"])

    auth_client.post(f"{API}/team-seasons/{demo.team_season.id}/make-current")
    me = auth_client.get(f"{API}/auth/me").json()
    blues = next(t for t in me["teams"] if t["team"]["slug"] == "blues")
    assert blues["current_team_season_id"] == demo.team_season.id


def test_player_create_with_squad_and_leave(auth_client: TestClient, db):
    from app.services.bootstrap import seed_club_structure

    ts = seed_club_structure(db)["blacks"]
    db.commit()
    r = auth_client.post(
        f"{API}/players", json={"first_name": "Archie", "team_season_id": ts.id, "squad_number": 9}
    )
    assert r.status_code == 201, r.text
    archie = r.json()
    assert archie["display_name"] == "Archie" and archie["cohort_id"] == ts.club_team.cohort_id

    squad = auth_client.get(f"{API}/team-seasons/{ts.id}/squad").json()
    assert [(m["player"]["display_name"], m["squad_number"]) for m in squad] == [("Archie", 9)]

    # Number clash is a 409 with a useful message
    max_ = auth_client.post(
        f"{API}/players", json={"first_name": "Max", "cohort_id": ts.club_team.cohort_id}
    ).json()
    r = auth_client.put(f"{API}/team-seasons/{ts.id}/squad/{max_['id']}", json={"squad_number": 9})
    assert r.status_code == 409 and "Archie" in r.json()["detail"]

    # Needs an age group one way or the other
    assert auth_client.post(f"{API}/players", json={"first_name": "Nobody"}).status_code == 422

    # Leaving is a date, not a delete
    r = auth_client.patch(f"{API}/players/{archie['id']}", json={"left_date": "2027-01-01"})
    assert r.json()["left_date"] == "2027-01-01"
    assert len(auth_client.get(f"{API}/players?include_left=false").json()) == 1
    assert len(auth_client.get(f"{API}/players").json()) == 2


def test_fixture_crud(auth_client: TestClient, db):
    from app.services.bootstrap import seed_club_structure, seed_reference_data

    seed_reference_data(db)
    ts = seed_club_structure(db)["blues"]
    db.commit()
    league = next(c for c in auth_client.get(f"{API}/competitions").json() if c["type"] == "league")
    team = auth_client.post(f"{API}/teams", json={"name": "Fleet Spurs"}).json()

    body = {
        "team_season_id": ts.id,
        "competition_id": league["id"],
        "opposition_team_id": team["id"],
        "kickoff_at": "2026-09-05T10:00:00",
        "venue": "away",
    }
    r = auth_client.post(f"{API}/fixtures", json=body)
    assert r.status_code == 201, r.text
    fx = r.json()
    assert (
        fx["match_number"] == 1
        and fx["status"] == "scheduled"
        and fx["opposition"]["name"] == "Fleet Spurs"
    )
    assert fx["appearances"] == [] and fx["goals"] == [] and fx["warnings"] == []

    fx2 = auth_client.post(
        f"{API}/fixtures", json=body | {"kickoff_at": "2026-09-12T10:00:00"}
    ).json()
    assert fx2["match_number"] == 2
    assert auth_client.post(f"{API}/fixtures", json=body | {"match_number": 1}).status_code == 409

    # Can't mark played without a score
    r = auth_client.patch(f"{API}/fixtures/{fx['id']}", json={"status": "played"})
    assert r.status_code == 422

    assert auth_client.delete(f"{API}/teams/{team['id']}").status_code == 409  # has fixtures
    assert auth_client.delete(f"{API}/fixtures/{fx['id']}").status_code == 204
    assert auth_client.delete(f"{API}/fixtures/{fx2['id']}").status_code == 204
    assert auth_client.delete(f"{API}/teams/{team['id']}").status_code == 204


def test_post_match_entry_flow(auth_client: TestClient, demo: DemoSeason):
    """The under-a-minute flow: one PUT with everything, then read it back and check stats moved."""
    fixture = next(f for f in demo.fixtures if f.match_number == 7)  # scheduled vs Fleet
    P = {name: p.id for name, p in demo.players.items()}
    coaches = demo.award_types["coaches_potm"].id
    parents = demo.award_types["parents_potm"].id

    payload = {
        "our_score": 2,
        "their_score": 1,
        "appearances": [
            {"player_id": P[n]}
            for n in ["Archie", "Max", "Noah", "Jack", "Ayla", "Kayson", "Stanley", "Teddy"]
        ],
        "goals": [
            {"scorer_id": P["Teddy"], "assisted_by_id": P["Archie"], "minute": 12},
            {"scorer_id": P["Archie"]},
        ],
        "awards": [
            {"award_type_id": coaches, "player_id": P["Teddy"]},
            {"award_type_id": parents, "player_id": P["Teddy"]},
            {"award_type_id": parents, "player_id": P["Archie"]},  # joint
        ],
    }
    r = auth_client.put(f"{API}/fixtures/{fixture.id}/result", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "played" and (d["our_score"], d["their_score"]) == (2, 1)
    assert len(d["appearances"]) == 8
    assert [
        (g["scorer"]["display_name"], g["assisted_by"] and g["assisted_by"]["display_name"])
        for g in d["goals"]
    ] == [("Teddy", "Archie"), ("Archie", None)]
    assert d["goals"][0]["minute"] == 12
    assert sorted((a["award_type"]["code"], a["player"]["display_name"]) for a in d["awards"]) == [
        ("coaches_potm", "Teddy"),
        ("parents_potm", "Archie"),
        ("parents_potm", "Teddy"),
    ]
    assert d["warnings"] == []

    # Stats reflect it: Archie 6 goals, 4 assists, 7 apps; Teddy 3 apps, 1 goal
    board = auth_client.get(f"{API}/team-seasons/{demo.team_season.id}/stats/leaderboard").json()
    rows = {r["player"]["display_name"]: r for r in board["rows"]}
    assert (rows["Archie"]["goals"], rows["Archie"]["assists"], rows["Archie"]["appearances"]) == (
        6,
        4,
        7,
    )
    assert (rows["Teddy"]["goals"], rows["Teddy"]["appearances"]) == (1, 3)
    summary = auth_client.get(f"{API}/team-seasons/{demo.team_season.id}/stats/summary").json()
    assert summary["overall"]["played"] == 7 and summary["overall"]["won"] == 3
    assert [f["result"] for f in summary["form"]] == ["L", "W", "L", "L", "W"]

    # Re-submitting replaces, not appends
    payload["goals"] = [{"scorer_id": P["Max"]}]
    payload["our_score"] = 1
    payload["awards"] = []
    d = auth_client.put(f"{API}/fixtures/{fixture.id}/result", json=payload).json()
    assert len(d["goals"]) == 1 and d["awards"] == []
    rows = {
        r["player"]["display_name"]: r
        for r in auth_client.get(
            f"{API}/team-seasons/{demo.team_season.id}/stats/leaderboard"
        ).json()["rows"]
    }
    assert rows["Archie"]["goals"] == 5

    # Scorer who didn't play is rejected
    payload["goals"] = [{"scorer_id": P["William"]}]
    r = auth_client.put(f"{API}/fixtures/{fixture.id}/result", json=payload)
    assert r.status_code == 422 and "William" in r.json()["detail"]

    # Score/scorer mismatch is a warning, not an error
    payload["goals"] = []
    payload["our_score"] = 2
    d = auth_client.put(f"{API}/fixtures/{fixture.id}/result", json=payload).json()
    assert d["warnings"] == ["0 of our 2 goals have a scorer recorded"]


def test_goal_input_validation(auth_client: TestClient, demo: DemoSeason):
    fixture = demo.fixtures[6]
    archie = demo.players["Archie"].id
    base = {"our_score": 1, "their_score": 0, "appearances": [{"player_id": archie}]}
    bad = [
        [{"scorer_id": archie, "assisted_by_id": archie}],
        [{"event_type": "opp_own_goal", "scorer_id": archie}],
        [{"event_type": "own_goal", "scorer_id": archie, "assisted_by_id": archie}],
        [{"event_type": "goal"}],
    ]
    for goals in bad:
        r = auth_client.put(f"{API}/fixtures/{fixture.id}/result", json=base | {"goals": goals})
        assert r.status_code == 422, goals
    r = auth_client.put(
        f"{API}/fixtures/{fixture.id}/result",
        json=base | {"goals": [{"event_type": "opp_own_goal"}]},
    )
    assert r.status_code == 200 and r.json()["goals"][0]["scorer"] is None


def test_fixture_detail_shape(auth_client: TestClient, demo: DemoSeason):
    fx = demo.fixtures[3]  # 5-0 vs Hook
    d = auth_client.get(f"{API}/fixtures/{fx.id}").json()
    assert (d["our_score"], d["their_score"]) == (5, 0)
    assert [g["scorer"]["display_name"] for g in d["goals"]] == [
        "Archie",
        "Archie",
        "Archie",
        "Ayla",
        "Kayson",
    ]
    assert [g["assisted_by"] and g["assisted_by"]["display_name"] for g in d["goals"]] == [
        "Max",
        "Max",
        None,
        "Noah",
        "Archie",
    ]
    assert len(d["appearances"]) == 9
    fixtures = auth_client.get(
        f"{API}/fixtures?team_season_id={demo.team_season.id}&status=played"
    ).json()
    assert len(fixtures) == 6


def test_player_stats_endpoint(auth_client: TestClient, demo: DemoSeason):
    r = auth_client.get(
        f"{API}/players/{demo.players['Archie'].id}/stats?team_season_id={demo.team_season.id}"
    )
    assert r.status_code == 200
    assert (r.json()["goals"], r.json()["squad_number"]) == (5, 2)
