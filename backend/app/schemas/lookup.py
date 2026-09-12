from pydantic import Field

from app.models.enums import AwardScope, CompetitionType, PositionCategory
from app.schemas.common import InputModel, ORMModel


class PositionRead(ORMModel):
    id: int
    code: str
    name: str
    category: PositionCategory
    sort_order: int


class CompetitionCreate(InputModel):
    name: str = Field(min_length=1, max_length=100)
    type: CompetitionType
    is_active: bool = True


class CompetitionUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: CompetitionType | None = None
    is_active: bool | None = None


class CompetitionRead(ORMModel):
    id: int
    name: str
    type: CompetitionType
    is_active: bool


class AwardTypeCreate(InputModel):
    name: str = Field(min_length=1, max_length=100, examples=["Most improved"])
    club_team_id: int | None = None  # None = club-wide (admins only)
    scope: AwardScope = AwardScope.MATCH


class AwardTypeUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class AwardTypeRead(ORMModel):
    id: int
    club_team_id: int | None
    code: str
    name: str
    scope: AwardScope
    sort_order: int
    is_active: bool
