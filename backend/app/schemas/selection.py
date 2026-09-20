from datetime import datetime

from pydantic import Field, model_validator

from app.models.enums import SelectionStatus
from app.schemas.common import InputModel, ORMModel
from app.schemas.player import PlayerSummary


class SelectionPlayerInput(InputModel):
    player_id: int
    status: SelectionStatus
    reason: str | None = Field(default=None, max_length=100, examples=["injured", "away"])


class SelectionSubmit(InputModel):
    """Availability for a match in one write - replaces what was there, like PUT /result."""

    players: list[SelectionPlayerInput] = []
    coaching: str | None = Field(default=None, max_length=200, examples=["Adam & Dan"])
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _no_duplicate_players(self):
        ids = [p.player_id for p in self.players]
        if len(ids) != len(set(ids)):
            raise ValueError("a player can only be selected once")
        return self


class SelectionPlayerRead(ORMModel):
    player: PlayerSummary
    squad_number: int | None
    status: SelectionStatus
    reason: str | None


class SelectionRead(ORMModel):
    """Available and unavailable players as two lists (squad-number then name order)."""

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
