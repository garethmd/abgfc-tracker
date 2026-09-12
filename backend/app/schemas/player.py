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
    # Which age group; defaults to the team-season's cohort when adding to a squad.
    cohort_id: int | None = None
    # Convenience: add to this team's squad on creation.
    team_season_id: int | None = None
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
    cohort_id: int | None
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
    team_season_id: int
    player: PlayerRead
    squad_number: int | None
    primary_position: PositionRead | None
    joined_at: date | None
    left_at: date | None


class MembershipRead(ORMModel):
    """A player's spell in one team-season, for their history."""

    id: int
    team_season_id: int
    team_id: int
    team_name: str
    team_slug: str
    season_name: str
    age_group: str | None
    squad_number: int | None
    joined_at: date | None
    left_at: date | None


class PlayerMove(InputModel):
    """Move a player between two teams' squads (same cohort) - an age-group coach action."""

    from_team_season_id: int
    to_team_season_id: int
    left_at: date | None = None
    squad_number: int | None = Field(default=None, ge=1, le=99)
