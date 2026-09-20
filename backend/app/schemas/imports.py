from datetime import date
from typing import Literal

from pydantic import Field

from app.models.enums import CompetitionType, FixtureStatus, Venue
from app.schemas.common import InputModel, ORMModel


class ImportPasteRequest(InputModel):
    text: str | None = Field(default=None, max_length=200_000)
    html: str | None = Field(default=None, max_length=2_000_000)


class Suggestion(ORMModel):
    id: int
    name: str
    confidence: float  # 1.0 exact, 0.9 token containment, else string ratio


class ImportRow(ORMModel):
    line: int
    date: date
    time: str | None
    home: str
    away: str
    our_venue: Venue | None = None
    opposition_raw: str | None = None
    opposition: Suggestion | None = None
    derby_club_team_id: int | None = None
    competition_raw: str | None = None
    competition: Suggestion | None = None
    venue_notes: str | None = None
    external_id: str | None = None
    status: FixtureStatus | None = None
    action: Literal["create", "existing", "conflict", "skip"]
    existing_fixture_id: int | None = None
    reason: str | None = None


class ImportPreview(ORMModel):
    team_season_id: int
    rows: list[ImportRow]
    counts: dict[str, int]


class ImportRowDecision(InputModel):
    """What the coach decided for one previewed row."""

    line: int
    action: Literal["create", "update", "skip"]
    date: date
    time: str | None = None
    our_venue: Venue | None = None
    venue_notes: str | None = None
    external_id: str | None = None
    status: FixtureStatus | None = None
    existing_fixture_id: int | None = None
    opposition_team_id: int | None = None
    new_opposition_name: str | None = Field(default=None, max_length=100)
    derby_club_team_id: int | None = None
    competition_id: int | None = None
    new_competition_name: str | None = Field(default=None, max_length=100)
    new_competition_type: CompetitionType | None = None


class ImportApply(InputModel):
    rows: list[ImportRowDecision]


class ImportResult(ORMModel):
    created: int
    updated: int
    skipped: int
    new_teams: list[str]
    new_competitions: list[str]
