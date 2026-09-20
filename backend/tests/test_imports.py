"""Fixture import from FA Full-Time: parsing, matching against what coaches already
entered, and a preview that never writes until confirmed."""

from datetime import date

from fastapi.testclient import TestClient

from app.services.bootstrap import DemoSeason, seed_club_structure
from app.services.imports import norm, parse_fa_fixtures, similarity

API = "/api/v1"

# Exactly what a coach gets from select-all + copy on the FA fixtures page.
BLACKS_TEXT = """Type	Date / Time	Home Team		Away Team	Venue	Competition	Status / Notes
L	19/09/26 08:00	Aldershot B&G U10M Blacks	Aldershot B&G U10M Blacks	VS	Mytchett Athletic U10M Kestrels	Mytchett Athletic U10M Kestrels	ALDERSHOT PARK	U10M Conference League Group Stage	
L	26/09/26 08:00	Aldershot B&G U10M Blacks	Aldershot B&G U10M Blacks	VS	Rushmoor Community U10M Mavericks	Rushmoor Community U10M Mavericks	ALDERSHOT PARK	U10M Pele	
L	17/10/26 08:00	Aldershot B&G U10M Blacks	Aldershot B&G U10M Blacks	VS	Aldershot B&G U10M Blues	Aldershot B&G U10M Blues	ALDERSHOT PARK	U10M Conference League Group Stage	
L	24/10/26 08:00	Badshot Lea U10M Stallions	Badshot Lea U10M Stallions	VS	Aldershot B&G U10M Blacks	Aldershot B&G U10M Blacks	WEYBOURNE RECREATION GROUND 3	U10M Pele	
L	05/12/26 00:00	Hook U10M Panthers	Hook U10M Panthers	VS	Aldershot B&G U10M Blacks	Aldershot B&G U10M Blacks	HARTLETTS PARK #1	U10M Pele	Postponed
L	12/12/26 08:00	Aldershot B&G U10M Blues	Aldershot B&G U10M Blues	VS	Fleet Spurs U10M Comets	Fleet Spurs U10M Comets	ALDERSHOT PARK	U10M Pele	
"""

BLACKS_HTML = """<table><tbody>
<tr><td><a href="/displayFixture.html?id=30422571">L</a></td><td><a href="/displayFixture.html?id=30422571"><span>19/09/26</span> <span>08:00</span></a></td>
<td class="home-team"><a href="/displayFixture.html?id=30422571">Aldershot B&amp;G U10M Blacks</a></td><td class="team-logo"><img alt="Aldershot B&amp;G U10M Blacks"></td>
<td class="score"><a>VS</a></td><td class="team-logo"><img alt="Mytchett Athletic U10M Kestrels"></td><td class="away-team"><a>Mytchett Athletic U10M Kestrels</a></td>
<td>ALDERSHOT PARK</td><td>U10M Conference League Group Stage</td><td></td></tr>
<tr><td><a href="/displayFixture.html?id=30422580">L</a></td><td><span>24/10/26</span> <span>08:00</span></td>
<td class="home-team">Badshot Lea U10M Stallions</td><td class="team-logo"><img alt="Badshot Lea U10M Stallions"></td>
<td class="score">VS</td><td class="team-logo"><img alt="Aldershot B&amp;G U10M Blacks"></td><td class="away-team">Aldershot B&amp;G U10M Blacks</td>
<td>WEYBOURNE RECREATION GROUND 3</td><td>U10M Pele</td><td></td></tr>
</tbody></table>"""


def test_parse_text():
    rows = parse_fa_fixtures(BLACKS_TEXT, None)
    assert len(rows) == 6
    r = rows[0]
    assert (r.date, r.time, r.home, r.away) == (
        date(2026, 9, 19),
        "08:00",
        "Aldershot B&G U10M Blacks",
        "Mytchett Athletic U10M Kestrels",
    )
    assert (
        r.venue == "ALDERSHOT PARK"
        and r.competition == "U10M Conference League Group Stage"
        and r.external_id is None
    )
    assert (
        rows[3].home == "Badshot Lea U10M Stallions" and rows[3].away == "Aldershot B&G U10M Blacks"
    )
    assert rows[4].time == "00:00" and rows[4].note == "Postponed"


def test_parse_html_keeps_fa_ids():
    rows = parse_fa_fixtures(None, BLACKS_HTML)
    assert [(r.external_id, r.home, r.away) for r in rows] == [
        ("30422571", "Aldershot B&G U10M Blacks", "Mytchett Athletic U10M Kestrels"),
        ("30422580", "Badshot Lea U10M Stallions", "Aldershot B&G U10M Blacks"),
    ]
    assert rows[0].venue == "ALDERSHOT PARK" and rows[1].competition == "U10M Pele"


def test_name_matching_against_real_coach_entries():
    assert norm("Mytchett Athletic U10M Kestrels") == norm("Mytchett athletic Kestrels")
    assert similarity("Hook U10M Tigers", "Hook Tigers") == 1.0
    assert similarity("Farnborough FC Juniors U10M Blues", "Farnborough Blues") == 0.9
    assert similarity("Haslemere Town U10M Harriers", "Haslemere Town Panthers") < 0.8
    assert similarity("Fleet Spurs U10M Comets", "Fleet Spurs Comets") == 1.0
    assert (
        similarity("Curley Park Rangers U10M Hawks", "CPR Hawks") < 0.8
    )  # abbreviations need a human


def _blacks(db, auth_client):
    ts = seed_club_structure(db)["blacks"]
    db.commit()
    return ts


def test_preview_classifies_rows(auth_client: TestClient, db, demo: DemoSeason):
    ts = _blacks(db, auth_client)
    # Coach already entered 19 Sep by hand with their own spelling and real kick-off time
    league = auth_client.post(
        f"{API}/competitions", json={"name": "Conference League", "type": "league"}
    ).json()
    kestrels = auth_client.post(f"{API}/teams", json={"name": "Mytchett athletic Kestrels"}).json()
    hand = auth_client.post(
        f"{API}/fixtures",
        json={
            "team_season_id": ts.id,
            "competition_id": league["id"],
            "opposition_team_id": kestrels["id"],
            "kickoff_at": "2026-09-19T09:00:00",
            "venue": "home",
        },
    ).json()
    # ...and a different opponent on 24 Oct (rearranged fixture)
    other = auth_client.post(f"{API}/teams", json={"name": "Someone Else"}).json()
    auth_client.post(
        f"{API}/fixtures",
        json={
            "team_season_id": ts.id,
            "competition_id": league["id"],
            "opposition_team_id": other["id"],
            "kickoff_at": "2026-10-24T09:00:00",
            "venue": "away",
        },
    )

    r = auth_client.post(
        f"{API}/team-seasons/{ts.id}/fixtures/import/preview", json={"text": BLACKS_TEXT}
    )
    assert r.status_code == 200, r.text
    p = r.json()
    by_line = {row["line"]: row for row in p["rows"]}
    assert p["counts"] == {"create": 3, "existing": 1, "conflict": 1, "skip": 1}

    ex = by_line[2]
    assert ex["action"] == "existing" and ex["existing_fixture_id"] == hand["id"]
    assert (
        ex["opposition"]["name"] == "Mytchett athletic Kestrels"
        and ex["opposition"]["confidence"] == 1.0
    )
    assert ex["competition"]["name"] == "Conference League"
    assert "fill in ground" in ex["reason"]

    new = by_line[3]
    assert new["action"] == "create" and new["our_venue"] == "home" and new["opposition"] is None
    assert new["competition_raw"] == "U10M Pele" and new["venue_notes"] == "Aldershot Park"

    derby = by_line[4]
    assert (
        derby["action"] == "create" and derby["derby_club_team_id"] == demo.team_season.club_team_id
    )

    conflict = by_line[5]
    assert conflict["action"] == "conflict" and "Someone Else" in conflict["reason"]

    assert (
        by_line[6]["action"] == "create"
        and by_line[6]["status"] == "postponed"
        and by_line[6]["our_venue"] == "away"
    )
    assert by_line[7]["action"] == "skip" and "Not a Blacks" in by_line[7]["reason"]

    # Preview wrote nothing
    assert len(auth_client.get(f"{API}/fixtures?team_season_id={ts.id}").json()) == 2


def test_apply_then_reimport_is_idempotent(auth_client: TestClient, db, demo: DemoSeason):
    ts = _blacks(db, auth_client)
    p = auth_client.post(
        f"{API}/team-seasons/{ts.id}/fixtures/import/preview",
        json={"text": BLACKS_TEXT, "html": BLACKS_HTML},
    ).json()
    # html wins when present: two rows with FA ids
    assert [r["external_id"] for r in p["rows"]] == ["30422571", "30422580"]

    decisions = []
    for row in p["rows"]:
        decisions.append(
            {
                "line": row["line"],
                "action": "create",
                "date": row["date"],
                "time": row["time"],
                "our_venue": row["our_venue"],
                "venue_notes": row["venue_notes"],
                "external_id": row["external_id"],
                "opposition_team_id": None,
                "new_opposition_name": row["opposition_raw"],
                "competition_id": None,
                "new_competition_name": row["competition_raw"]
                .replace("U10M ", "")
                .replace(" Group Stage", ""),
                "new_competition_type": "league",
            }
        )
    r = auth_client.post(f"{API}/team-seasons/{ts.id}/fixtures/import", json={"rows": decisions})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 2
    assert r.json()["new_teams"] == [
        "Mytchett Athletic Kestrels",
        "Badshot Lea Stallions",
    ]  # age token dropped
    fx = auth_client.get(f"{API}/fixtures?team_season_id={ts.id}").json()
    assert [(f["match_number"], f["venue"], f["external_id"], f["kickoff_at"]) for f in fx] == [
        (1, "home", "30422571", "2026-09-19T08:00:00"),
        (2, "away", "30422580", "2026-10-24T08:00:00"),
    ]

    # Same paste again: everything is "existing", nothing to change
    p2 = auth_client.post(
        f"{API}/team-seasons/{ts.id}/fixtures/import/preview", json={"html": BLACKS_HTML}
    ).json()
    assert p2["counts"]["existing"] == 2 and all(
        "nothing to change" in r["reason"] for r in p2["rows"]
    )


def test_import_requires_coach_and_rejects_junk(
    client: TestClient, auth_client: TestClient, db, demo: DemoSeason
):
    from app.models import RoleScope, UserRole
    from tests.conftest import login_as, make_user

    ts = _blacks(db, auth_client)
    r = auth_client.post(
        f"{API}/team-seasons/{ts.id}/fixtures/import/preview", json={"text": "hello\nworld"}
    )
    assert r.status_code == 422
    make_user(db, "viewer", (UserRole.VIEWER, RoleScope.TEAM, ts.club_team_id))
    db.commit()
    login_as(client, "viewer")
    assert (
        client.post(
            f"{API}/team-seasons/{ts.id}/fixtures/import/preview", json={"text": BLACKS_TEXT}
        ).status_code
        == 403
    )


def test_merge_duplicate_opposition(auth_client: TestClient, demo: DemoSeason):
    """'Hook Tigers' and 'Hook U10M Tigers' were both created by hand; fold one into the other."""
    hook = demo.teams["Hook Juniors"]  # has fixtures 4 (played) and 8 (postponed)
    dup = auth_client.post(
        f"{API}/teams", json={"name": "Hook U10M Juniors", "short_name": "Hook"}
    ).json()
    league = demo.competitions["League"].id
    auth_client.post(
        f"{API}/fixtures",
        json={
            "team_season_id": demo.team_season.id,
            "competition_id": league,
            "opposition_team_id": dup["id"],
            "kickoff_at": "2026-11-28T10:00:00",
            "venue": "away",
        },
    )
    assert (
        auth_client.post(
            f"{API}/teams/{dup['id']}/merge", json={"into_team_id": dup["id"]}
        ).status_code
        == 422
    )
    r = auth_client.post(f"{API}/teams/{dup['id']}/merge", json={"into_team_id": hook.id})
    assert r.status_code == 200, r.text
    assert r.json()["short_name"] == "Hook"  # blank on the target, filled from the source
    assert auth_client.get(f"{API}/teams/{dup['id']}").status_code == 404
    h = auth_client.get(f"{API}/teams/{hook.id}/head-to-head").json()
    assert h["record"]["played"] == 1 and len(h["upcoming"]) == 1 and len(h["other"]) == 1
