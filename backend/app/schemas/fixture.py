from datetime import datetime

from pydantic import Field, model_validator

from app.models.enums import FixtureStatus, Venue
from app.schemas.common import InputModel, ORMModel
from app.schemas.lookup import AwardTypeRead, CompetitionRead, PositionRead
from app.schemas.player import PlayerSummary
from app.schemas.team import TeamRead


class FixtureCreate(InputModel):
    team_season_id: int
    competition_id: int
    opposition_team_id: int
    match_number: int | None = Field(default=None, ge=1)
    kickoff_at: datetime
    venue: Venue = Venue.HOME
    venue_notes: str | None = Field(default=None, max_length=200)
    status: FixtureStatus = FixtureStatus.SCHEDULED
    duration_minutes: int | None = Field(default=None, ge=10, le=120)
    notes: str | None = None


class FixtureUpdate(InputModel):
    competition_id: int | None = None
    opposition_team_id: int | None = None
    match_number: int | None = Field(default=None, ge=1)
    kickoff_at: datetime | None = None
    venue: Venue | None = None
    venue_notes: str | None = Field(default=None, max_length=200)
    status: FixtureStatus | None = None
    our_score: int | None = Field(default=None, ge=0)
    their_score: int | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=10, le=120)
    notes: str | None = None


class FixtureRead(ORMModel):
    id: int
    team_season_id: int
    competition: CompetitionRead
    opposition: TeamRead
    match_number: int | None
    kickoff_at: datetime
    venue: Venue
    venue_notes: str | None
    status: FixtureStatus
    our_score: int | None
    their_score: int | None
    duration_minutes: int | None
    notes: str | None


class AppearanceRead(ORMModel):
    id: int
    player: PlayerSummary
    started: bool
    position: PositionRead | None
    shirt_number: int | None
    captain: bool


class GoalRead(ORMModel):
    """A goal event with its assist folded in - the shape the UI wants."""

    id: int
    event_type: str  # goal | own_goal | opp_own_goal
    scorer: PlayerSummary | None
    assisted_by: PlayerSummary | None
    assist_event_id: int | None
    minute: int | None
    sequence: int
    notes: str | None


class AwardRead(ORMModel):
    id: int
    award_type: AwardTypeRead
    player: PlayerSummary
    fixture_id: int | None
    period_label: str | None
    notes: str | None


class FixtureDetail(FixtureRead):
    appearances: list[AppearanceRead]
    goals: list[GoalRead]
    awards: list[AwardRead]
    warnings: list[str]  # e.g. goal events don't add up to the stored score


# --- Post-match entry ------------------------------------------------------


class AppearanceInput(InputModel):
    player_id: int
    started: bool = True
    position_id: int | None = None
    shirt_number: int | None = Field(default=None, ge=1, le=99)
    captain: bool = False


class GoalInput(InputModel):
    """scorer_id None + event_type opp_own_goal = opposition own goal."""

    event_type: str = Field(default="goal", pattern="^(goal|own_goal|opp_own_goal)$")
    scorer_id: int | None = None
    assisted_by_id: int | None = None
    minute: int | None = Field(default=None, ge=0, le=130)
    notes: str | None = None

    @model_validator(mode="after")
    def _check_scorer(self):
        if self.event_type == "opp_own_goal":
            if self.scorer_id is not None or self.assisted_by_id is not None:
                raise ValueError("opposition own goals have no scorer or assist")
        elif self.scorer_id is None:
            raise ValueError("scorer_id is required")
        if self.event_type == "own_goal" and self.assisted_by_id is not None:
            raise ValueError("own goals cannot be assisted")
        if self.scorer_id is not None and self.scorer_id == self.assisted_by_id:
            raise ValueError("a player cannot assist their own goal")
        return self


class AwardInput(InputModel):
    award_type_id: int
    player_id: int


class ResultSubmit(InputModel):
    """The whole result of a match in one transactional write."""

    our_score: int = Field(ge=0)
    their_score: int = Field(ge=0)
    appearances: list[AppearanceInput]
    goals: list[GoalInput] = []
    awards: list[AwardInput] = []

    @model_validator(mode="after")
    def _no_duplicate_players(self):
        ids = [a.player_id for a in self.appearances]
        if len(ids) != len(set(ids)):
            raise ValueError("a player can only appear once")
        return self


# --- Live match entry ------------------------------------------------------
# Same end state as ResultSubmit, written one tap at a time (services/live.py).


class LiveSquad(InputModel):
    """Who is playing today. Captain, if given, must be one of them."""

    player_ids: list[int] = Field(min_length=1)
    captain_id: int | None = None

    @model_validator(mode="after")
    def _check(self):
        if len(self.player_ids) != len(set(self.player_ids)):
            raise ValueError("a player can only appear once")
        if self.captain_id is not None and self.captain_id not in self.player_ids:
            raise ValueError("the captain must be playing")
        return self


class LiveGoal(GoalInput):
    """A goal as it happens. `sequence` is the client's next event sequence: resending the
    same one (a retried request) returns the goal already recorded instead of a second."""

    sequence: int = Field(ge=1)
