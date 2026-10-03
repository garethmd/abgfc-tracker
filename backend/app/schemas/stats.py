from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.player import PlayerSummary


class TeamRecord(BaseModel):
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    win_pct: float  # 0-100, 0.0 when nothing played


class FormEntry(BaseModel):
    fixture_id: int
    kickoff_at: datetime
    opposition: str
    our_score: int
    their_score: int
    result: Literal["W", "D", "L"]


class AwardCount(BaseModel):
    award_type_id: int
    award_type_code: str
    count: int


class PlayerStatsRow(BaseModel):
    player: PlayerSummary
    # The player's own number - a guest keeps the one they wear for their own team.
    squad_number: int | None
    appearances: int
    starts: int
    goals: int
    assists: int
    own_goals: int
    goals_per_game: float
    awards: list[AwardCount]
    minutes: int | None  # None until stints are recorded
    # Played for this team without being in its squad (guesting from another team).
    is_guest: bool = False


class PlayerTeamStats(BaseModel):
    """One team a player has turned out for in a season - their own or as a guest."""

    team_season_id: int
    club_team_id: int
    team_name: str
    team_slug: str
    squad_number: int | None
    is_guest: bool
    appearances: int
    starts: int
    goals: int
    assists: int


class PlayerTotals(BaseModel):
    """A player's season across every team in the age group they turned out for."""

    appearances: int
    starts: int
    goals: int
    assists: int
    own_goals: int
    goals_per_game: float
    awards: list[AwardCount]


class PlayerSeasonStats(BaseModel):
    """The headline (every team) plus the split by team, for one player in one season."""

    season_id: int
    totals: PlayerTotals
    teams: list[PlayerTeamStats]


class HighlightTile(BaseModel):
    label: str
    value: int
    players: list[PlayerSummary]  # every name on a tie; empty when nothing recorded


class SeasonSummary(BaseModel):
    team_season_id: int
    overall: TeamRecord
    league: TeamRecord
    form: list[FormEntry]  # last 5, most recent last
    highlights: list[HighlightTile]


class Leaderboard(BaseModel):
    team_season_id: int
    competition_type: str | None
    award_types: list[AwardCount]  # column headers (count = 0) - keeps the table shape stable
    rows: list[PlayerStatsRow]


class CohortTeamRecord(BaseModel):
    team_season_id: int
    club_team_id: int
    team_name: str
    overall: TeamRecord
    league: TeamRecord
    form: list[FormEntry]
    squad_size: int


class CohortPlayerRow(BaseModel):
    """A player's appearances across every team in the age group - the fairness view."""

    player: PlayerSummary
    teams: list[str]
    appearances: int
    starts: int
    goals: int
    assists: int
    minutes: int | None


class CohortOverview(BaseModel):
    cohort_id: int
    season_id: int
    teams: list[CohortTeamRecord]
    players: list[CohortPlayerRow]
