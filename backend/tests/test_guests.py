"""Guest appearances: a child playing for another team in the same age group.

The club does this most weeks - the Blues lend a player to the Blacks. The appearance and
any goals belong to the team they turned out for, the player keeps their own squad number,
and everything still adds up on the player's own page and in the age-group overview.
"""

from fastapi.testclient import TestClient

from app.services.bootstrap import DemoSeason

API = "/api/v1"


def _reds_ts(client: TestClient) -> int:
    team = client.get(f"{API}/club-teams/by-slug/reds").json()
    return client.get(f"{API}/club-teams/{team['id']}/seasons").json()[0]["id"]


def _fixture_for(client: TestClient, ts: int, demo: DemoSeason, opponent: str) -> int:
    opp = client.post(f"{API}/teams", json={"name": opponent}).json()
    r = client.post(
        f"{API}/fixtures",
        json={
            "team_season_id": ts,
            "competition_id": next(iter(demo.competitions.values())).id,
            "opposition_team_id": opp["id"],
            "kickoff_at": "2026-10-03T10:00:00",
            "venue": "home",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _guest_result(client: TestClient, fixture_id: int, player_id: int):
    return client.put(
        f"{API}/fixtures/{fixture_id}/result",
        json={
            "our_score": 1,
            "their_score": 0,
            "appearances": [{"player_id": player_id, "started": True}],
            "goals": [{"event_type": "goal", "scorer_id": player_id}],
            "awards": [],
        },
    )


def test_a_guest_counts_for_the_team_they_played_for(auth_client: TestClient, demo: DemoSeason):
    reds = _reds_ts(auth_client)
    fx = _fixture_for(auth_client, reds, demo, "Guest Town")
    archie = demo.players["Archie"]  # a Blues squad player, number 1

    assert _guest_result(auth_client, fx, archie.id).status_code == 200

    rows = auth_client.get(f"{API}/team-seasons/{reds}/stats/leaderboard").json()["rows"]
    guest = next(r for r in rows if r["player"]["id"] == archie.id)
    assert guest["is_guest"] is True
    assert guest["appearances"] == 1 and guest["goals"] == 1
    # Numbers belong to the player across the age group, so he keeps his Blues one.
    blues_squad = auth_client.get(f"{API}/team-seasons/{demo.team_season.id}/squad").json()
    his_number = next(m["squad_number"] for m in blues_squad if m["player"]["id"] == archie.id)
    assert his_number is not None and guest["squad_number"] == his_number

    # His own team's record is untouched - a Reds appearance is not a Blues appearance.
    blues = auth_client.get(f"{API}/team-seasons/{demo.team_season.id}/stats/leaderboard").json()
    own = next(r for r in blues["rows"] if r["player"]["id"] == archie.id)
    assert own["is_guest"] is False and own["appearances"] == 6 and own["goals"] == 5


def test_the_player_page_adds_up_across_teams(auth_client: TestClient, demo: DemoSeason):
    reds = _reds_ts(auth_client)
    fx = _fixture_for(auth_client, reds, demo, "Guest Rovers")
    archie = demo.players["Archie"]
    _guest_result(auth_client, fx, archie.id)

    r = auth_client.get(
        f"{API}/players/{archie.id}/season-stats", params={"season_id": demo.season.id}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # The headline is the footballer, not the team: both spells added together.
    assert body["totals"]["appearances"] == 7 and body["totals"]["goals"] == 6
    assert body["totals"]["assists"] == 3
    assert body["totals"]["goals_per_game"] == round(6 / 7, 2)
    # Awards are summed across teams by type.
    coaches = next(a for a in body["totals"]["awards"] if a["award_type_code"] == "coaches_potm")
    assert coaches["count"] == 2

    by_team = {t["team_name"]: t for t in body["teams"]}
    assert by_team["Blues"]["is_guest"] is False and by_team["Blues"]["goals"] == 5
    assert by_team["Reds"]["is_guest"] is True and by_team["Reds"]["goals"] == 1
    # He keeps his own number in both rows.
    assert by_team["Reds"]["squad_number"] == by_team["Blues"]["squad_number"]
    # Own team first, guest spells after.
    assert [t["team_name"] for t in body["teams"]][0] == "Blues"

    # The age-group overview already totalled both; it should still agree.
    cohort_id = auth_client.get(f"{API}/cohorts").json()[0]["id"]
    ov = auth_client.get(
        f"{API}/cohorts/{cohort_id}/overview", params={"season_id": demo.season.id}
    ).json()
    agg = next(p for p in ov["players"] if p["player"]["id"] == archie.id)
    assert agg["appearances"] == 7 and agg["goals"] == 6
    assert sorted(agg["teams"]) == ["Blues", "Reds"]


def test_a_player_from_another_age_group_is_refused(auth_client: TestClient, demo: DemoSeason):
    other = auth_client.post(
        f"{API}/cohorts", json={"name": "Born 2014/15", "birth_year_start": 2014}
    ).json()
    outsider = auth_client.post(
        f"{API}/players", json={"first_name": "Outsider", "cohort_id": other["id"]}
    ).json()
    fx = _fixture_for(auth_client, _reds_ts(auth_client), demo, "Guest United")

    r = _guest_result(auth_client, fx, outsider["id"])
    assert r.status_code == 422 and "age group" in r.json()["detail"]

    live = auth_client.post(
        f"{API}/fixtures/{fx}/live/start", json={"player_ids": [outsider["id"]]}
    )
    assert live.status_code == 422 and "age group" in live.json()["detail"]


def test_the_matchday_sheet_leaves_guests_out(auth_client: TestClient, demo: DemoSeason):
    """The sheet plans this team's own squad - a guest would skew the fairness shading."""
    from io import BytesIO

    from pypdf import PdfReader

    reds = _reds_ts(auth_client)
    for name in ("Jackson", "Adrian"):
        auth_client.post(f"{API}/players", json={"first_name": name, "team_season_id": reds})
    played = _fixture_for(auth_client, reds, demo, "Guest Albion")
    _guest_result(auth_client, played, demo.players["Archie"].id)
    _fixture_for(auth_client, reds, demo, "Next Opponent")

    r = auth_client.get(f"{API}/team-seasons/{reds}/reports/matchday.pdf")
    assert r.status_code == 200, r.text
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(r.content)).pages)
    # Two squad players, not three: the guest is not on the team sheet.
    assert "SQUAD  ·  2 PLAYERS" in text
    # He is still named as the scorer of the last match, which is right - he scored it.
    assert "Archie" in text
