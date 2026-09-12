from datetime import date

from pydantic import Field

from app.schemas.common import InputModel, ORMModel
from app.schemas.lookup import PositionRead


class PlayerCreate(InputModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str | None = Field(default=None, max_length=50)
    display_name: str | None = Field(default=None, max_length=50)
    date_of_birth: date | None = None
    joined_date: date | None = None
    notes: str | None = None
    # Convenience: add to this season's squad on creation.
    season_id: int | None = None
    squad_number: int | None = Field(default=None, ge=1, le=99)


class PlayerUpdate(InputModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, max_length=50)
    display_name: str | None = Field(default=None, max_length=50)
    date_of_birth: date | None = None
    joined_date: date | None = None
    left_date: date | None = None
    notes: str | None = None


class PlayerRead(ORMModel):
    id: int
    first_name: str
    last_name: str | None
    display_name: str
    date_of_birth: date | None
    joined_date: date | None
    left_date: date | None
    notes: str | None


class PlayerSummary(ORMModel):
    """Lightweight embed for nested responses."""

    id: int
    display_name: str


class SquadMemberUpsert(InputModel):
    squad_number: int | None = Field(default=None, ge=1, le=99)
    primary_position_id: int | None = None
    joined_at: date | None = None
    left_at: date | None = None


class SquadMemberRead(ORMModel):
    id: int
    season_id: int
    player: PlayerRead
    squad_number: int | None
    primary_position: PositionRead | None
    joined_at: date | None
    left_at: date | None
