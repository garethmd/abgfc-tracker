from datetime import datetime

from pydantic import Field

from app.schemas.common import InputModel, ORMModel
from app.schemas.player import PlayerSummary


class SelectionSubmit(InputModel):
    """Availability for a match in one write - replaces what was there, like PUT /result.
    Everyone in the squad is available unless listed here."""

    unavailable_player_ids: list[int] = []
    coaching: str | None = Field(default=None, max_length=200, examples=["Adam & Dan"])
    notes: str | None = Field(default=None, max_length=5000)


class SelectionPlayerRead(ORMModel):
    player: PlayerSummary
    squad_number: int | None


class SelectionRead(ORMModel):
    """Who can play (the squad minus those marked unavailable) and who can't, both in
    squad-number then name order."""

    fixture_id: int
    available: list[SelectionPlayerRead]
    unavailable: list[SelectionPlayerRead]
    arrival_at: datetime  # kick-off minus the team-season's lead time
    arrival_lead_minutes: int
    coaching: str | None
    notes: str | None
    updated_at: datetime


class ParentsMessage(ORMModel):
    text: str
