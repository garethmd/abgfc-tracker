"""Pre-match squad selection and the parents' message."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.models import RoleScope, UserRole, Venue
from app.services.bootstrap import DemoSeason
from app.services.messages import (
    MessageInput,
    SquadLine,
    arrival_time,
    format_kickoff,
    kickoff_article,
    parents_message,
)
from tests.conftest import login_as, make_user

API = "/api/v1"

# The real message this feature reproduces (see the brief).
EXAMPLE = """REDS are home against Haslemere Town Panthers
This is an 11am kick off at Aldershot Park
Please arrive at 10.30
Adam & Dan coaching
Squad
Jackson
Adrian
Ashton
Austin
Eli
Ellis
Harrison
Joe
Logan
Oscar"""

SQUAD = [
    "Jackson",
    "Adrian",
    "Ashton",
    "Austin",
    "Eli",
    "Ellis",
    "Harrison",
    "Joe",
    "Logan",
    "Oscar",
]


# --- the template, as pure functions --------------------------------------------------


def _example(**over) -> MessageInput:
    base = dict(
        team_name="Reds",
        venue=Venue.HOME,
        opposition="Haslemere Town Panthers",
        kickoff=datetime(2026, 9, 26, 11, 0),
        ground="Aldershot Park",
        arrival=datetime(2026, 9, 26, 10, 30),
        coaching="Adam & Dan",
        squad=[SquadLine(n) for n in SQUAD[:7]] + [SquadLine(n, sub=True) for n in SQUAD[7:]],
        notes=None,
    )
    base.update(over)
    return MessageInput(**base)


def test_message_matches_the_real_example():
    assert parents_message(_example()) == EXAMPLE


def test_message_variants():
    assert parents_message(_example(venue=Venue.AWAY)).splitlines()[0] == (
        "REDS are away against Haslemere Town Panthers"
    )
    assert parents_message(_example(venue=Venue.NEUTRAL)).splitlines()[0] == (
        "REDS are playing Haslemere Town Panthers"
    )
    # No ground: the " at ..." goes, nothing else moves
    assert parents_message(_example(ground=None)).splitlines()[1] == "This is an 11am kick off"
    assert parents_message(_example(ground="  ")).splitlines()[1] == "This is an 11am kick off"
    # 10.30 kick-off: "a", minutes shown, arrive on the hour written as "10"
    lines = parents_message(
        _example(kickoff=datetime(2026, 9, 26, 10, 30), arrival=datetime(2026, 9, 26, 10, 0))
    ).splitlines()
    assert lines[1] == "This is a 10.30am kick off at Aldershot Park"
    assert lines[2] == "Please arrive at 10"
    # No coaches line when empty - and no blank line left behind
    lines = parents_message(_example(coaching=None)).splitlines()
    assert lines[3] == "Squad" and "" not in lines
    assert "coaching" not in parents_message(_example(coaching="  "))
    # Notes follow the squad after exactly one blank line, verbatim
    text = parents_message(_example(notes="Bring both kits\nCar park is the far one"))
    assert text == EXAMPLE + "\n\nBring both kits\nCar park is the far one"
    assert text.count("\n\n") == 1
    # Date line first
    assert parents_message(_example(), date_line=True) == "Saturday 26 September\n" + EXAMPLE
    # Subs marked
    lines = parents_message(_example(), mark_subs=True).splitlines()
    assert lines[5:12] == SQUAD[:7] and lines[12:] == ["Joe (sub)", "Logan (sub)", "Oscar (sub)"]


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (11, 0, "an 11am"),
        (10, 30, "a 10.30am"),
        (14, 0, "a 2pm"),
        (8, 15, "an 8.15am"),
        (12, 0, "a 12pm"),
        (0, 30, "a 12.30am"),
        (18, 0, "a 6pm"),
    ],
)
def test_kickoff_wording(hour, minute, expected):
    dt = datetime(2026, 9, 26, hour, minute)
    assert f"{kickoff_article(dt)} {format_kickoff(dt)}" == expected


def test_arrival_arithmetic():
    assert arrival_time(datetime(2026, 9, 26, 11, 0), 30) == datetime(2026, 9, 26, 10, 30)
    assert arrival_time(datetime(2026, 9, 26, 10, 0), 45) == datetime(2026, 9, 26, 9, 15)
    # Across midnight
    assert arrival_time(datetime(2026, 9, 27, 0, 15), 30) == datetime(2026, 9, 26, 23, 45)
    # Clocks go forward at 01:00 on 29 March 2026: 01:xx doesn't exist, so 30 minutes
    # before 02:15 BST is 00:45 GMT on the wall clock.
    assert arrival_time(datetime(2026, 3, 29, 2, 15), 30) == datetime(2026, 3, 29, 0, 45)
    # Clocks go back at 02:00 on 25 October 2026: an ordinary morning kick-off that day
    # is still plain wall-clock arithmetic.
    assert arrival_time(datetime(2026, 10, 25, 10, 0), 30) == datetime(2026, 10, 25, 9, 30)


# --- the API ---------------------------------------------------------------------------


def _reds_fixture(client: TestClient, demo: DemoSeason, **over) -> tuple[int, dict[str, int]]:
    """The example set up for real: Reds at home to Haslemere Town Panthers, 11am at
    Aldershot Park, ten players (Jackson wears 1, the rest have no number yet)."""
    team = client.get(f"{API}/club-teams/by-slug/reds").json()
    ts = client.get(f"{API}/club-teams/{team['id']}/seasons").json()[0]
    players = {}
    for name in SQUAD:
        r = client.post(
            f"{API}/players",
            json={
                "first_name": name,
                "team_season_id": ts["id"],
                "squad_number": 1 if name == "Jackson" else None,
            },
        )
        assert r.status_code == 201, r.text
        players[name] = r.json()["id"]
    opp = client.post(f"{API}/teams", json={"name": "Haslemere Town Panthers"}).json()
    comp = next(iter(demo.competitions.values()))
    body = {
        "team_season_id": ts["id"],
        "competition_id": comp.id,
        "opposition_team_id": opp["id"],
        "kickoff_at": "2026-09-26T11:00:00",
        "venue": "home",
        "venue_notes": "Aldershot Park",
        **over,
    }
    r = client.post(f"{API}/fixtures", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"], players


def _submit(players: dict[str, int], starters=SQUAD[:7], subs=SQUAD[7:], out=(), **extra):
    return {
        "players": [{"player_id": players[n], "status": "start"} for n in starters]
        + [{"player_id": players[n], "status": "sub"} for n in subs]
        + [{"player_id": players[n], "status": "unavailable", "reason": "injured"} for n in out],
        **extra,
    }


def test_select_squad_and_message(auth_client: TestClient, demo: DemoSeason):
    fx, P = _reds_fixture(auth_client, demo)
    url = f"{API}/fixtures/{fx}/selection"
    assert auth_client.get(url).json() is None
    assert auth_client.get(f"{url}/message").status_code == 404

    r = auth_client.put(url, json=_submit(P, coaching="Adam & Dan"))
    assert r.status_code == 200, r.text
    sel = r.json()
    assert [p["player"]["display_name"] for p in sel["starters"]] == SQUAD[:7]
    assert [p["player"]["display_name"] for p in sel["subs"]] == SQUAD[7:]
    assert sel["unavailable"] == []
    assert sel["starters"][0]["squad_number"] == 1 and sel["starters"][1]["squad_number"] is None
    assert sel["arrival_at"] == "2026-09-26T10:30:00" and sel["arrival_lead_minutes"] == 30
    assert sel["coaching"] == "Adam & Dan" and sel["notes"] is None
    assert auth_client.get(url).json() == sel

    assert auth_client.get(f"{url}/message").json()["text"] == EXAMPLE
    text = auth_client.get(f"{url}/message", params={"mark_subs": True, "date_line": True}).json()
    assert text["text"].startswith("Saturday 26 September\nREDS") and "Oscar (sub)" in text["text"]


def test_selection_is_replaced_whole(auth_client: TestClient, demo: DemoSeason):
    fx, P = _reds_fixture(auth_client, demo)
    url = f"{API}/fixtures/{fx}/selection"
    auth_client.put(url, json=_submit(P, coaching="Adam", notes="Bring both kits"))
    # Second save: Oscar is out, Logan now starts, no coaching line, notes kept
    r = auth_client.put(
        url,
        json=_submit(
            P, starters=SQUAD[:6] + ["Logan"], subs=["Joe"], out=["Oscar"], notes="Bring both kits"
        ),
    )
    sel = r.json()
    assert len(sel["starters"]) == 7 and [p["player"]["display_name"] for p in sel["subs"]] == [
        "Joe"
    ]
    assert sel["unavailable"][0]["player"]["display_name"] == "Oscar"
    assert sel["unavailable"][0]["reason"] == "injured"
    assert sel["coaching"] is None
    lines = auth_client.get(f"{url}/message").json()["text"].splitlines()
    assert lines[3] == "Squad" and "Oscar" not in lines and lines[-1] == "Bring both kits"
    assert lines[-2] == ""

    # Empty save is allowed (coach cleared everyone but kept the notes)
    r = auth_client.put(url, json={"players": [], "notes": "TBC"})
    assert r.status_code == 200 and r.json()["starters"] == []
    assert auth_client.delete(url).status_code == 204
    assert auth_client.get(url).json() is None
    assert auth_client.delete(url).status_code == 404


def test_selection_validation(auth_client: TestClient, demo: DemoSeason):
    fx, P = _reds_fixture(auth_client, demo)
    url = f"{API}/fixtures/{fx}/selection"
    # Duplicate player
    body = _submit(P)
    body["players"].append({"player_id": P["Jackson"], "status": "sub"})
    assert auth_client.put(url, json=body).status_code == 422
    # Bad status
    r = auth_client.put(url, json={"players": [{"player_id": P["Jackson"], "status": "bench"}]})
    assert r.status_code == 422
    # Unknown player
    assert (
        auth_client.put(url, json={"players": [{"player_id": 9999, "status": "start"}]}).status_code
        == 404
    )
    # A child from another age group can't be picked
    other = auth_client.post(f"{API}/cohorts", json={"name": "Born 2015/16"}).json()
    stranger = auth_client.post(
        f"{API}/players", json={"first_name": "Zed", "cohort_id": other["id"]}
    ).json()
    r = auth_client.put(url, json={"players": [{"player_id": stranger["id"], "status": "start"}]})
    assert r.status_code == 422 and "age group" in r.json()["detail"]
    # Someone else in the cohort but not in the squad is fine (borrowed from another team)
    blues_kid = demo.players["Archie"].id
    r = auth_client.put(url, json={"players": [{"player_id": blues_kid, "status": "sub"}]})
    assert r.status_code == 200 and r.json()["subs"][0]["squad_number"] is None
    # Once played, the plan is frozen
    played = demo.fixtures[0]
    r = auth_client.put(f"{API}/fixtures/{played.id}/selection", json={"players": []})
    assert r.status_code == 409


def test_selection_does_not_touch_the_result(auth_client: TestClient, demo: DemoSeason):
    """A plan is not an appearance: entering the result afterwards is unchanged."""
    fx, P = _reds_fixture(auth_client, demo)
    auth_client.put(f"{API}/fixtures/{fx}/selection", json=_submit(P))
    assert auth_client.get(f"{API}/fixtures/{fx}").json()["appearances"] == []
    r = auth_client.put(
        f"{API}/fixtures/{fx}/result",
        json={
            "our_score": 1,
            "their_score": 0,
            "appearances": [{"player_id": P["Oscar"]}],  # only the sub turned up
            "goals": [{"scorer_id": P["Oscar"]}],
        },
    )
    assert r.status_code == 200, r.text
    assert [a["player"]["display_name"] for a in r.json()["appearances"]] == ["Oscar"]
    # The plan is still there to look back on, but can't be edited any more
    sel = auth_client.get(f"{API}/fixtures/{fx}/selection").json()
    assert len(sel["starters"]) == 7
    assert auth_client.put(f"{API}/fixtures/{fx}/selection", json=_submit(P)).status_code == 409


def test_selection_goes_with_the_fixture(auth_client: TestClient, demo: DemoSeason):
    fx, P = _reds_fixture(auth_client, demo)
    auth_client.put(f"{API}/fixtures/{fx}/selection", json=_submit(P))
    assert auth_client.delete(f"{API}/fixtures/{fx}").status_code == 204
    assert auth_client.get(f"{API}/fixtures/{fx}/selection").status_code == 404


def test_arrival_lead_time_is_a_team_setting(auth_client: TestClient, demo: DemoSeason):
    fx, P = _reds_fixture(auth_client, demo, kickoff_at="2026-09-26T10:30:00")
    url = f"{API}/fixtures/{fx}/selection"
    ts = auth_client.get(f"{API}/fixtures/{fx}").json()["team_season_id"]
    assert auth_client.get(f"{API}/team-seasons/{ts}").json()["arrival_lead_minutes"] == 30
    r = auth_client.patch(f"{API}/team-seasons/{ts}", json={"arrival_lead_minutes": 45})
    assert r.status_code == 200 and r.json()["arrival_lead_minutes"] == 45
    auth_client.put(url, json=_submit(P))
    sel = auth_client.get(url).json()
    assert sel["arrival_at"] == "2026-09-26T09:45:00" and sel["arrival_lead_minutes"] == 45
    lines = auth_client.get(f"{url}/message").json()["text"].splitlines()
    assert lines[1] == "This is a 10.30am kick off at Aldershot Park"
    assert lines[2] == "Please arrive at 9.45"
    assert (
        auth_client.patch(
            f"{API}/team-seasons/{ts}", json={"arrival_lead_minutes": 500}
        ).status_code
        == 422
    )


def test_selection_scoping(client: TestClient, auth_client: TestClient, db, demo: DemoSeason):
    fx, P = _reds_fixture(auth_client, demo)
    reds = client.get(f"{API}/club-teams/by-slug/reds").json()["id"]
    blues = demo.team_season.club_team_id
    make_user(db, "reds_viewer", (UserRole.VIEWER, RoleScope.TEAM, reds))
    make_user(db, "reds_coach", (UserRole.COACH, RoleScope.TEAM, reds))
    make_user(db, "blues_coach", (UserRole.COACH, RoleScope.TEAM, blues))
    db.commit()
    url = f"{API}/fixtures/{fx}/selection"

    login_as(client, "reds_coach")
    assert client.put(url, json=_submit(P, coaching="Adam & Dan")).status_code == 200
    assert client.get(f"{url}/message").status_code == 200

    login_as(client, "reds_viewer")
    assert client.get(url).status_code == 200
    assert len(client.get(url).json()["starters"]) == 7
    assert client.put(url, json=_submit(P)).status_code == 403
    assert client.delete(url).status_code == 403
    assert client.get(f"{url}/message").status_code == 403  # names children; coaches only

    login_as(client, "blues_coach")
    assert client.get(url).status_code == 403
    assert client.put(url, json=_submit(P)).status_code == 403
    assert client.get(f"{url}/message").status_code == 403


def test_matchday_sheet_shows_the_selection(auth_client: TestClient, demo: DemoSeason):
    """Selected players are pre-ticked on the sheet; it stays one page."""
    import io

    from pypdf import PdfReader

    fixture = next(f for f in demo.fixtures if f.match_number == 7)  # scheduled v Fleet
    names = list(demo.players)
    P = {n: p.id for n, p in demo.players.items()}
    r = auth_client.put(
        f"{API}/fixtures/{fixture.id}/selection",
        json=_submit(P, starters=names[:7], subs=names[7:10], out=names[10:], coaching="Gareth"),
    )
    assert r.status_code == 200, r.text
    r = auth_client.get(
        f"{API}/team-seasons/{demo.team_season.id}/reports/matchday.pdf",
        params={"fixture_id": fixture.id},
    )
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1
    text = "\n".join(p.extract_text() for p in reader.pages)
    assert "Squad selected: 7 starting, 3 subs" in text
    assert "arrive 9.30" in text and "Gareth coaching" in text
    assert "Ticked = selected" in text
