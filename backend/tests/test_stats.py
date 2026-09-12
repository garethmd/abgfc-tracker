"""The derived numbers are the point of the app. Expected values are hand-checked
against the demo season documented in app/services/bootstrap.py."""

from datetime import datetime

import pytest

from app.models import Appearance, Fixture, FixtureStatus, MatchEvent, Player, PlayerStint, Team
from app.services import stats
from app.services.bootstrap import DemoSeason
from app.services.stats import StatsService


def _row(board, name):
    return next(r for r in board.rows if r.player.display_name == name)


def _award(row, code):
    return next(a.count for a in row.awards if a.award_type_code == code)


# --- pure functions ----------------------------------------------------------


@pytest.mark.parametrize(
    "ours,theirs,expected", [(3, 1, "W"), (2, 2, "D"), (0, 4, "L"), (0, 0, "D")]
)
def test_outcome(ours, theirs, expected):
    assert stats.outcome(ours, theirs) == expected


def test_team_record_empty():
    rec = stats.team_record([])
    assert rec.model_dump() == {
        "played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "win_pct": 0.0,
    }


def test_team_record_ignores_unplayed_and_scoreless():
    def fx(status, ours, theirs):
        return Fixture(
            status=status, our_score=ours, their_score=theirs, kickoff_at=datetime(2026, 9, 1)
        )

    rec = stats.team_record(
        [
            fx(FixtureStatus.PLAYED, 2, 0),
            fx(FixtureStatus.SCHEDULED, None, None),
            fx(FixtureStatus.POSTPONED, None, None),
            fx(FixtureStatus.PLAYED, None, None),  # marked played but no score yet
            fx(FixtureStatus.ABANDONED, 1, 1),
        ]
    )
    assert (rec.played, rec.won, rec.goals_for) == (1, 1, 2)
    assert rec.win_pct == 100.0


def test_minutes_from_stints():
    def app_with(*stints):
        return Appearance(stints=[PlayerStint(on_minute=a, off_minute=b) for a, b in stints])

    assert stats.minutes_for_appearance(Appearance(stints=[]), 50) is None
    assert stats.minutes_for_appearance(app_with((0, None)), 50) == 50
    assert stats.minutes_for_appearance(app_with((0, 25), (35, None)), 50) == 40
    assert stats.minutes_for_appearance(app_with((10, 30)), 50) == 20
    # Clipped to the match length if someone forgot to sub off in the data.
    assert stats.minutes_for_appearance(app_with((40, 60)), 50) == 10


def test_highlights_tie_lists_every_name_and_zero_is_empty():
    from app.models import AwardType
    from app.schemas.player import PlayerSummary
    from app.schemas.stats import AwardCount, PlayerStatsRow

    def row(name, goals, assists, potm):
        return PlayerStatsRow(
            player=PlayerSummary(id=hash(name) % 1000, display_name=name),
            squad_number=None,
            appearances=1,
            starts=1,
            goals=goals,
            assists=assists,
            own_goals=0,
            goals_per_game=goals,
            awards=[AwardCount(award_type_id=1, award_type_code="coaches_potm", count=potm)],
            minutes=None,
        )

    at = AwardType(id=1, code="coaches_potm", name="Coaches' POTM")
    tiles = stats.highlights([row("Zed", 2, 0, 0), row("Amy", 2, 0, 0), row("Bob", 1, 0, 0)], [at])
    top, assists, potm = tiles
    assert (top.value, [p.display_name for p in top.players]) == (2, ["Amy", "Zed"])
    assert (assists.value, assists.players) == (0, [])
    assert (potm.label, potm.value, potm.players) == ("Coaches' POTM", 0, [])


# --- against the demo season ----------------------------------------------------


def test_season_summary_records(db, demo: DemoSeason):
    s = StatsService(db).season_summary(demo.season.id)

    assert s.overall.model_dump() == {
        "played": 6,
        "won": 2,
        "drawn": 1,
        "lost": 3,
        "goals_for": 12,
        "goals_against": 12,
        "goal_difference": 0,
        "win_pct": 33.3,
    }
    assert s.league.model_dump() == {
        "played": 4,
        "won": 2,
        "drawn": 1,
        "lost": 1,
        "goals_for": 11,
        "goals_against": 6,
        "goal_difference": 5,
        "win_pct": 50.0,
    }


def test_form_is_last_five_chronological(db, demo: DemoSeason):
    s = StatsService(db).season_summary(demo.season.id)
    assert [f.result for f in s.form] == ["D", "L", "W", "L", "L"]
    assert s.form[-1].opposition == "Farnborough Town Youth"
    assert (s.form[-1].our_score, s.form[-1].their_score) == (1, 3)


def test_highlights_from_demo(db, demo: DemoSeason):
    s = StatsService(db).season_summary(demo.season.id)
    by_label = {t.label: t for t in s.highlights}
    names = lambda t: [p.display_name for p in t.players]  # noqa: E731

    assert (by_label["Top scorer"].value, names(by_label["Top scorer"])) == (5, ["Archie"])
    assert (by_label["Most assists"].value, names(by_label["Most assists"])) == (
        3,
        ["Archie", "Max"],
    )
    assert names(by_label["Coaches' Player of the Match"]) == ["Archie"]
    assert by_label["Coaches' Player of the Match"].value == 2
    assert names(by_label["Parents' Player of the Match"]) == ["Max", "Noah"]


EXPECTED_ALL = {
    # name: (apps, goals, assists, own_goals, coaches, parents)
    "Archie": (6, 5, 3, 0, 2, 0),
    "Max": (6, 2, 3, 0, 1, 2),
    "Noah": (6, 2, 2, 0, 1, 2),
    "Jack": (5, 0, 1, 0, 1, 1),
    "Ayla": (5, 1, 0, 0, 0, 1),
    "Kayson": (5, 1, 0, 0, 0, 1),
    "Stanley": (5, 0, 0, 1, 1, 0),
    "Alexander": (5, 0, 0, 0, 0, 0),
    "William": (5, 0, 0, 0, 0, 0),
    "Reece": (4, 0, 0, 0, 0, 0),
    "Teddy": (2, 0, 0, 0, 0, 0),
}


def test_leaderboard_all_competitions(db, demo: DemoSeason):
    board = StatsService(db).leaderboard(demo.season.id)
    assert len(board.rows) == 11
    for name, (apps, g, a, og, coaches, parents) in EXPECTED_ALL.items():
        r = _row(board, name)
        assert (r.appearances, r.goals, r.assists, r.own_goals) == (apps, g, a, og), name
        assert (_award(r, "coaches_potm"), _award(r, "parents_potm")) == (coaches, parents), name
        assert r.minutes is None  # no stints recorded yet
    assert _row(board, "Archie").goals_per_game == 0.83
    assert _row(board, "Teddy").goals_per_game == 0.0
    # Sorted by goals, then assists, then appearances, then name.
    assert [r.player.display_name for r in board.rows[:4]] == ["Archie", "Max", "Noah", "Ayla"]
    assert [a.award_type_code for a in board.award_types] == ["coaches_potm", "parents_potm"]


EXPECTED_LEAGUE = {
    "Archie": (4, 5, 3),
    "Max": (4, 1, 3),
    "Noah": (4, 2, 1),
    "Jack": (3, 0, 1),
    "Ayla": (3, 1, 0),
    "Kayson": (4, 1, 0),
    "Stanley": (3, 0, 0),
    "Alexander": (3, 0, 0),
    "William": (3, 0, 0),
    "Reece": (2, 0, 0),
    "Teddy": (0, 0, 0),
}


def test_leaderboard_league_only(db, demo: DemoSeason):
    board = StatsService(db).leaderboard(demo.season.id, competition_type="league")
    for name, (apps, g, a) in EXPECTED_LEAGUE.items():
        r = _row(board, name)
        assert (r.appearances, r.goals, r.assists) == (apps, g, a), name
    assert _row(board, "Stanley").own_goals == 0  # the own goal was in a friendly
    assert _award(_row(board, "Jack"), "coaches_potm") == 0  # cup award excluded


def test_empty_season_is_all_zeros(db, demo: DemoSeason):
    from app.models import Season

    empty = Season(name="2027/28")
    db.add(empty)
    db.commit()
    svc = StatsService(db)
    s = svc.season_summary(empty.id)
    assert s.overall.played == 0 and s.form == []
    assert all(t.value == 0 and t.players == [] for t in s.highlights)
    assert svc.leaderboard(empty.id).rows == []


def test_player_who_left_squad_still_counts(db, demo: DemoSeason):
    """Appearances belong to the fixture, so a player removed from the squad keeps their stats."""
    from app.repositories.players import SquadRepository

    member = SquadRepository(db).get_member(demo.season.id, demo.players["Reece"].id)
    db.delete(member)
    db.commit()
    board = StatsService(db).leaderboard(demo.season.id)
    r = _row(board, "Reece")
    assert (r.appearances, r.squad_number) == (4, None)


def test_minutes_appear_once_every_appearance_has_stints(db, demo: DemoSeason):
    teddy = demo.players["Teddy"]
    apps = [a for f in demo.fixtures for a in f.appearances if a.player_id == teddy.id]
    assert len(apps) == 2
    apps[0].stints.append(PlayerStint(on_minute=0, off_minute=25))
    db.commit()
    assert StatsService(db).player_season(teddy.id, demo.season.id).minutes is None
    apps[1].stints.append(PlayerStint(on_minute=10, off_minute=None))
    db.commit()
    assert StatsService(db).player_season(teddy.id, demo.season.id).minutes == 25 + 40


def test_score_warnings(db, demo: DemoSeason):
    f = demo.fixtures[0]  # 3-1, three goal events
    assert stats.score_warnings(f) == []
    f.our_score = 4
    assert stats.score_warnings(f) == ["3 of our 4 goals have a scorer recorded"]
    f.our_score = 4
    f.events.append(
        MatchEvent(
            event_type="goal",
            player=demo.players["Teddy"],
            player_id=demo.players["Teddy"].id,
            sequence=9,
        )
    )
    assert stats.score_warnings(f) == ["Teddy has a goal but no appearance"]
    f.our_score = 3
    assert stats.score_warnings(f)[0] == "4 goals recorded but our score is 3"


def test_team_and_player_orm_smoke(db):
    db.add(Team(name="X"))
    db.add(Player(first_name="A", display_name="A"))
    db.commit()
