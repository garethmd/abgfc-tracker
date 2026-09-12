from pydantic import Field

from app.schemas.common import InputModel, ORMModel


class TeamCreate(InputModel):
    name: str = Field(min_length=1, max_length=100)
    short_name: str | None = Field(default=None, max_length=30)
    colours: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class TeamUpdate(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    short_name: str | None = Field(default=None, max_length=30)
    colours: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class TeamRead(ORMModel):
    id: int
    name: str
    short_name: str | None
    colours: str | None
    notes: str | None
