from pydantic import Field, model_validator

from app.schemas.common import InputModel, ORMModel
from app.schemas.season import SeasonRead


class CohortCreate(InputModel):
    name: str = Field(min_length=1, max_length=50, examples=["Born 2016/17"])
    birth_year_start: int | None = Field(default=None, ge=2000, le=2100)


class CohortUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    birth_year_start: int | None = Field(default=None, ge=2000, le=2100)
    is_active: bool | None = None


class CohortRead(ORMModel):
    id: int
    name: str
    birth_year_start: int | None
    is_active: bool


class ClubTeamCreate(InputModel):
    cohort_id: int
    name: str = Field(min_length=1, max_length=50, examples=["Blacks"])
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,50}$")
    colour: str | None = Field(default=None, max_length=30)
    sort_order: int = 0


class ClubTeamUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]{1,50}$")
    colour: str | None = Field(default=None, max_length=30)
    sort_order: int | None = None
    is_active: bool | None = None


class ClubTeamRead(ORMModel):
    id: int
    cohort_id: int
    name: str
    slug: str
    colour: str | None
    sort_order: int
    is_active: bool


class TeamSeasonRead(ORMModel):
    id: int
    club_team: ClubTeamRead
    season: SeasonRead
    age_group: str | None
    format: str | None
    match_minutes: int
    is_current: bool
    arrival_lead_minutes: int  # "Please arrive at" = kick-off minus this


class TeamSeasonStart(InputModel):
    """Start a team's participation in a season. Give an existing season_id or a new
    season_name; optionally copy the squad forward from a previous team-season."""

    season_id: int | None = None
    season_name: str | None = Field(default=None, min_length=1, max_length=20, examples=["2027/28"])
    age_group: str | None = Field(default=None, max_length=10)
    format: str | None = Field(default=None, max_length=10, examples=["7v7", "9v9"])
    match_minutes: int = Field(default=50, ge=10, le=120)
    copy_squad_from_team_season_id: int | None = None
    make_current: bool = True

    @model_validator(mode="after")
    def _one_season_ref(self):
        if (self.season_id is None) == (self.season_name is None):
            raise ValueError("give exactly one of season_id or season_name")
        return self


class TeamSeasonUpdate(InputModel):
    age_group: str | None = Field(default=None, max_length=10)
    format: str | None = Field(default=None, max_length=10)
    match_minutes: int | None = Field(default=None, ge=10, le=120)
    arrival_lead_minutes: int | None = Field(default=None, ge=0, le=180)
