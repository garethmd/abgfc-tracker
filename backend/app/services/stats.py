"""Derived statistics.

Everything here is a pure function over already-loaded rows so the arithmetic can be
tested without a database. `StatsService` at the bottom wires the repositories in.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from app.models import (
    Appearance,
    AwardType,
    CompetitionType,
    EventType,
    Fixture,
    FixtureStatus,
    MatchEvent,
    Player,
)
from app.models import Award as AwardModel
from app.repositories.fixtures import FixtureRepository
from app.repositories.lookups import AwardTypeRepository
from app.repositories.players import SquadRepository
from app.repositories.seasons import SeasonRepository
from app.repositories.stats import StatsRepository
from app.schemas.player import PlayerSummary
from app.schemas.stats import (
    AwardCount,
    FormEntry,
    HighlightTile,
    Leaderboard,
    PlayerStatsRow,
    SeasonSummary,
    TeamRecord,
)

Result = Literal["W", "D", "L"]


def outcome(our_score: int, their_score: int) -> Result:
    if our_score > their_score:
        return "W"
    if our_score < their_score:
        return "L"
    return "D"


def _is_played(f: Fixture) -> bool:
    return (
        f.status == FixtureStatus.PLAYED and f.our_score is not None and f.their_score is not None
    )


def team_record(fixtures: Iterable[Fixture]) -> TeamRecord:
    played = won = drawn = lost = gf = ga = 0
    for f in fixtures:
        if not _is_played(f):
            continue
        played += 1
        gf += f.our_score
        ga += f.their_score
        match outcome(f.our_score, f.their_score):
            case "W":
                won += 1
            case "D":
                drawn += 1
            case "L":
                lost += 1
    return TeamRecord(
        played=played,
        won=won,
        drawn=drawn,
        lost=lost,
        goals_for=gf,
        goals_against=ga,
        goal_difference=gf - ga,
        win_pct=round(100 * won / played, 1) if played else 0.0,
    )


def form(fixtures: Iterable[Fixture], n: int = 5) -> list[FormEntry]:
    """Last `n` played fixtures in chronological order (most recent last)."""
    played = sorted((f for f in fixtures if _is_played(f)), key=lambda f: (f.kickoff_at, f.id))
    return [
        FormEntry(
            fixture_id=f.id,
            kickoff_at=f.kickoff_at,
            opposition=f.opposition.name,
            our_score=f.our_score,
            their_score=f.their_score,
            result=outcome(f.our_score, f.their_score),
        )
        for f in played[-n:]
    ]


def minutes_for_appearance(appearance: Appearance, match_duration: int) -> int | None:
    """Sum of stints, clipped to the match length. None when no stints are recorded."""
    if not appearance.stints:
        return None
    total = 0
    for stint in appearance.stints:
        off = stint.off_minute if stint.off_minute is not None else match_duration
        total += max(0, min(off, match_duration) - stint.on_minute)
    return total


def goals_from_events(events: Iterable[MatchEvent]) -> tuple[int, int]:
    """(our goals, their goals) implied by the event log."""
    ours = theirs = 0
    for e in events:
        if e.event_type in (EventType.GOAL, EventType.OPP_OWN_GOAL):
            ours += 1
        elif e.event_type == EventType.OWN_GOAL:
            theirs += 1
    return ours, theirs


def score_warnings(fixture: Fixture) -> list[str]:
    """Human-readable mismatches between the stored score and the event log."""
    if not _is_played(fixture):
        return []
    warnings: list[str] = []
    ours, theirs = goals_from_events(fixture.events)
    if ours < fixture.our_score:
        warnings.append(f"{ours} of our {fixture.our_score} goals have a scorer recorded")
    elif ours > fixture.our_score:
        warnings.append(f"{ours} goals recorded but our score is {fixture.our_score}")
    if theirs > fixture.their_score:
        warnings.append(
            f"{theirs} own goals recorded but opposition score is {fixture.their_score}"
        )
    appearance_ids = {a.player_id for a in fixture.appearances}
    for e in fixture.events:
        if e.player_id is not None and e.player_id not in appearance_ids:
            name = e.player.display_name if e.player else f"player {e.player_id}"
            warnings.append(f"{name} has a {e.event_type.replace('_', ' ')} but no appearance")
            break
    return warnings


@dataclass
class _Tally:
    appearances: int = 0
    starts: int = 0
    goals: int = 0
    assists: int = 0
    own_goals: int = 0
    awards: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    minutes: int = 0
    minutes_complete: bool = True


def player_rows(
    players: Sequence[Player],
    appearances: Sequence[Appearance],
    events: Sequence[MatchEvent],
    awards: Sequence[AwardModel],
    award_types: Sequence[AwardType],
    squad_numbers: dict[int, int | None] | None = None,
    durations: dict[int, int] | None = None,
) -> list[PlayerStatsRow]:
    """One row per player. `players` is the base set (so a fresh squad shows zeros);
    anyone else with an appearance/event/award in the data is added too."""
    squad_numbers = squad_numbers or {}
    durations = durations or {}
    tallies: dict[int, _Tally] = defaultdict(_Tally)
    by_id: dict[int, Player] = {p.id: p for p in players}

    for a in appearances:
        t = tallies[a.player_id]
        t.appearances += 1
        if a.started:
            t.starts += 1
        mins = minutes_for_appearance(a, durations.get(a.fixture_id, 0))
        if mins is None:
            t.minutes_complete = False
        else:
            t.minutes += mins
        by_id.setdefault(a.player_id, a.player)

    for e in events:
        if e.player_id is None:
            continue
        t = tallies[e.player_id]
        match e.event_type:
            case EventType.GOAL:
                t.goals += 1
            case EventType.ASSIST:
                t.assists += 1
            case EventType.OWN_GOAL:
                t.own_goals += 1
        if e.player_id not in by_id and e.player is not None:
            by_id[e.player_id] = e.player

    for aw in awards:
        tallies[aw.player_id].awards[aw.award_type_id] += 1
        if aw.player_id not in by_id and aw.player is not None:
            by_id[aw.player_id] = aw.player

    rows: list[PlayerStatsRow] = []
    for pid, player in by_id.items():
        t = tallies.get(pid, _Tally())
        rows.append(
            PlayerStatsRow(
                player=PlayerSummary.model_validate(player),
                squad_number=squad_numbers.get(pid),
                appearances=t.appearances,
                starts=t.starts,
                goals=t.goals,
                assists=t.assists,
                own_goals=t.own_goals,
                goals_per_game=round(t.goals / t.appearances, 2) if t.appearances else 0.0,
                awards=[
                    AwardCount(
                        award_type_id=at.id, award_type_code=at.code, count=t.awards.get(at.id, 0)
                    )
                    for at in award_types
                ],
                minutes=t.minutes if (t.appearances and t.minutes_complete) else None,
            )
        )
    rows.sort(key=lambda r: (-r.goals, -r.assists, -r.appearances, r.player.display_name.lower()))
    return rows


def highlights(
    rows: Sequence[PlayerStatsRow], award_types: Sequence[AwardType]
) -> list[HighlightTile]:
    """Top scorer / most assists / most of each award. Ties list every name."""

    def tile(label: str, value_of) -> HighlightTile:
        best = max((value_of(r) for r in rows), default=0)
        winners = [r.player for r in rows if best > 0 and value_of(r) == best]
        winners.sort(key=lambda p: p.display_name.lower())
        return HighlightTile(label=label, value=best, players=winners)

    tiles = [
        tile("Top scorer", lambda r: r.goals),
        tile("Most assists", lambda r: r.assists),
    ]
    for at in award_types:
        tiles.append(
            tile(
                at.name,
                lambda r, at_id=at.id: next(
                    (a.count for a in r.awards if a.award_type_id == at_id), 0
                ),
            )
        )
    return tiles


# --- DB-backed orchestration ------------------------------------------------


class StatsService:
    def __init__(self, db: Session):
        self.db = db
        self.seasons = SeasonRepository(db)
        self.fixtures = FixtureRepository(db)
        self.squad = SquadRepository(db)
        self.award_types = AwardTypeRepository(db)
        self.stats = StatsRepository(db)

    def season_summary(self, season_id: int) -> SeasonSummary:
        self.seasons.get_or_404(season_id)
        played = self.fixtures.list_played(season_id)
        league = [f for f in played if f.competition.type == CompetitionType.LEAGUE]
        rows, award_types = self._rows(season_id, None)
        return SeasonSummary(
            season_id=season_id,
            overall=team_record(played),
            league=team_record(league),
            form=form(played),
            highlights=highlights(rows, award_types),
        )

    def leaderboard(self, season_id: int, competition_type: str | None = None) -> Leaderboard:
        self.seasons.get_or_404(season_id)
        rows, award_types = self._rows(season_id, competition_type)
        return Leaderboard(
            season_id=season_id,
            competition_type=competition_type,
            award_types=[
                AwardCount(award_type_id=a.id, award_type_code=a.code, count=0) for a in award_types
            ],
            rows=rows,
        )

    def player_season(self, player_id: int, season_id: int) -> PlayerStatsRow | None:
        rows, _ = self._rows(season_id, None)
        return next((r for r in rows if r.player.id == player_id), None)

    def _rows(
        self, season_id: int, competition_type: str | None
    ) -> tuple[list[PlayerStatsRow], list[AwardType]]:
        season = self.seasons.get_or_404(season_id)
        fixture_ids = self.fixtures.played_fixture_ids(season_id, competition_type)
        members = self.squad.list_for_season(season_id)
        award_types = self.award_types.list_all(active_only=True)
        durations = {
            f.id: f.duration_minutes or season.match_minutes
            for f in self.fixtures.list_played(season_id)
        }
        rows = player_rows(
            players=[m.player for m in members],
            appearances=self.stats.appearances_for(fixture_ids),
            events=self.stats.events_for(fixture_ids),
            awards=self.stats.match_awards_for(fixture_ids),
            award_types=award_types,
            squad_numbers={m.player_id: m.squad_number for m in members},
            durations=durations,
        )
        return rows, award_types
