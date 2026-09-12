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


class AwardTypeRead(ORMModel):
    id: int
    code: str
    name: str
    scope: AwardScope
    sort_order: int
    is_active: bool
