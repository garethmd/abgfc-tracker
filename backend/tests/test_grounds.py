"""Default home grounds: ours and the opposition's.

The ground is copied onto a fixture when it is created, never looked up afterwards, so a
one-off venue (a waterlogged pitch, a cup tie somewhere neutral) survives any later change
to the team's default.
"""

from fastapi.testclient import TestClient

from app.services.bootstrap import DemoSeason

API = "/api/v1"


def _setup(client: TestClient, demo: DemoSeason) -> tuple[int, int, int]:
    """Our team season with a home ground, and an opposition with theirs."""
    ts = demo.team_season.id
    club_team_id = demo.team_season.club_team_id
    r = client.patch(f"{API}/club-teams/{club_team_id}", json={"home_ground": "Aldershot Park"})
    assert r.status_code == 200, r.text
    opp = client.post(
        f"{API}/teams", json={"name": "Hook Tigers", "home_ground": "Hook Junior School 7v7"}
    ).json()
    return ts, club_team_id, opp["id"]


def _fixture(client: TestClient, demo: DemoSeason, ts: int, opp_id: int, **over) -> dict:
    body = {
        "team_season_id": ts,
        "competition_id": next(iter(demo.competitions.values())).id,
        "opposition_team_id": opp_id,
        "kickoff_at": "2026-11-07T10:00:00",
        "venue": "home",
        **over,
    }
    r = client.post(f"{API}/fixtures", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_new_fixture_takes_the_right_ground(auth_client: TestClient, demo: DemoSeason):
    ts, _, opp = _setup(auth_client, demo)
    assert _fixture(auth_client, demo, ts, opp)["venue_notes"] == "Aldershot Park"
    away = _fixture(auth_client, demo, ts, opp, venue="away", kickoff_at="2026-11-14T10:00:00")
    assert away["venue_notes"] == "Hook Junior School 7v7"
    # Neutral belongs to neither of them.
    neutral = _fixture(
        auth_client, demo, ts, opp, venue="neutral", kickoff_at="2026-11-21T10:00:00"
    )
    assert neutral["venue_notes"] is None


def test_the_fixture_always_wins(auth_client: TestClient, demo: DemoSeason):
    """A ground given on the fixture is never second-guessed - that is the override."""
    ts, club_team_id, opp = _setup(auth_client, demo)
    f = _fixture(auth_client, demo, ts, opp, venue_notes="Waverley Abbey Junior School")
    assert f["venue_notes"] == "Waverley Abbey Junior School"

    # Waterlogged: the coach moves this one match. Changing the club default afterwards
    # must not touch it.
    auth_client.patch(f"{API}/club-teams/{club_team_id}", json={"home_ground": "Somewhere Else"})
    assert auth_client.get(f"{API}/fixtures/{f['id']}").json()["venue_notes"] == (
        "Waverley Abbey Junior School"
    )

    # An explicit blank stays blank too.
    r = auth_client.patch(f"{API}/fixtures/{f['id']}", json={"venue_notes": None})
    assert r.json()["venue_notes"] is None


def test_switching_venue_fills_an_empty_ground(auth_client: TestClient, demo: DemoSeason):
    ts, _, opp = _setup(auth_client, demo)
    f = _fixture(auth_client, demo, ts, opp)
    r = auth_client.patch(f"{API}/fixtures/{f['id']}", json={"venue": "away", "venue_notes": None})
    assert r.json()["venue_notes"] == "Hook Junior School 7v7"


def test_import_prefers_the_fa_venue_and_learns_a_new_one(
    auth_client: TestClient, demo: DemoSeason
):
    """The FA's venue is for that match, so it wins; where we have nothing, we learn it."""
    ts, _, _ = _setup(auth_client, demo)
    text = (
        "Type\tDate / Time\tHome Team\t\tAway Team\tVenue\tCompetition\tStatus / Notes\n"
        "L\t05/12/26 10:00\tLiss Athletic U10M Leopards\t\tVS\t\tAldershot B&G U10M Blues"
        "\tNewman Collard Park\tCup\t"
    )
    pre = auth_client.post(
        f"{API}/team-seasons/{ts}/fixtures/import/preview", json={"text": text}
    ).json()
    row = pre["rows"][0]
    assert row["action"] == "create" and row["ground_note"] is None  # we know nothing yet

    decisions = {
        "rows": [
            {
                "line": row["line"],
                "action": "create",
                "date": row["date"],
                "time": row["time"],
                "our_venue": row["our_venue"],
                "venue_notes": row["venue_notes"],
                "new_opposition_name": row["opposition_raw"],
                "competition_id": next(iter(demo.competitions.values())).id,
            }
        ]
    }
    res = auth_client.post(f"{API}/team-seasons/{ts}/fixtures/import", json=decisions).json()
    assert res["created"] == 1
    assert res["grounds_learned"] == ["Liss Athletic Leopards"]
    team = next(
        t for t in auth_client.get(f"{API}/teams").json() if t["name"] == "Liss Athletic Leopards"
    )
    assert team["home_ground"] == "Newman Collard Park"


def test_import_flags_a_venue_that_disagrees(auth_client: TestClient, demo: DemoSeason):
    """The Haslemere case: the FA listed an away game at our own ground."""
    ts, _, opp = _setup(auth_client, demo)
    text = (
        "Type\tDate / Time\tHome Team\t\tAway Team\tVenue\tCompetition\tStatus / Notes\n"
        "L\t12/12/26 10:00\tHook U10M Tigers\t\tVS\t\tAldershot B&G U10M Blues"
        "\tAldershot Park\tCup\t"
    )
    row = auth_client.post(
        f"{API}/team-seasons/{ts}/fixtures/import/preview", json={"text": text}
    ).json()["rows"][0]
    assert row["ground_note"] == "FA says Aldershot Park; we have them at Hook Junior School 7v7"
    # Advisory only - the FA value is still what would be imported.
    assert row["venue_notes"] == "Aldershot Park"
