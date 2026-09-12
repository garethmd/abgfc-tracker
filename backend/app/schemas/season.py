from datetime import date

from pydantic import Field

from app.schemas.common import InputModel, ORMModel


class SeasonCreate(InputModel):
    name: str = Field(min_length=1, max_length=20, examples=["2026/27"])
    start_date: date | None = None
    end_date: date | None = None


class SeasonUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    start_date: date | None = None
    end_date: date | None = None


class SeasonRead(ORMModel):
    id: int
    name: str
    start_date: date | None
    end_date: date | None
