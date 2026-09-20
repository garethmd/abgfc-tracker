from datetime import datetime

from pydantic import Field

from app.schemas.common import InputModel, ORMModel
from app.schemas.stats import TeamRecord


class TeamCreate(InputModel):
    name: str = Field(min_length=1, max_length=100)
    short_name: str | None = Field(default=None, max_length=30)
    colours: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class TeamUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    short_name: str | None = Field(default=None, max_length=30)
    colours: str | None = Field(default=None, max_length=50)
    notes: str | None = None
    club_team_id: int | None = None  # link a derby opponent to our own team


class TeamMerge(InputModel):
    """Fold this opposition team into another (fixtures re-pointed, this row deleted)."""

    into_team_id: int


class TeamRead(ORMModel):
    id: int
    club_team_id: int | None = None  # set when the opposition is one of our own teams
    name: str
    short_name: str | None
    colours: str | None
    notes: str | None


class HeadToHeadFixture(ORMModel):
    """A fixture against this opposition, with enough context to list across seasons."""

    id: int
    team_season_id: int
    club_team_id: int
    club_team_name: str
    season_name: str
    competition_name: str
    match_number: int | None
    kickoff_at: datetime
    venue: str
    venue_notes: str | None
    status: str
    our_score: int | None
    their_score: int | None
    result: str | None  # W / D / L for played fixtures


class HeadToHead(ORMModel):
    team: TeamRead
    record: TeamRecord
    form: list[str]  # results v this opposition, oldest first
    played: list[HeadToHeadFixture]  # most recent first
    upcoming: list[HeadToHeadFixture]  # soonest first
    other: list[HeadToHeadFixture]  # postponed / cancelled / abandoned
