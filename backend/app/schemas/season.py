from datetime import date

from pydantic import Field

from app.schemas.common import InputModel, ORMModel


class SeasonCreate(InputModel):
    name: str = Field(min_length=1, max_length=20, examples=["2026/27"])
    start_date: date | None = None
    end_date: date | None = None
    match_minutes: int = Field(default=50, ge=10, le=120)
    is_current: bool = False


class SeasonUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    match_minutes: int | None = Field(default=None, ge=10, le=120)


class SeasonRead(ORMModel):
    id: int
    name: str
    start_date: date | None
    end_date: date | None
    match_minutes: int
    is_current: bool
