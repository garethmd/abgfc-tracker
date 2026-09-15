from datetime import datetime

from pydantic import Field

from app.schemas.common import InputModel, ORMModel


class MatchNoteCreate(InputModel):
    body: str = Field(min_length=1, max_length=20000)
    author: str | None = Field(default=None, max_length=100, examples=["Stuart"])
    sent_at: datetime | None = None


class MatchNoteUpdate(InputModel):
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    author: str | None = Field(default=None, max_length=100)
    sent_at: datetime | None = None


class MatchNoteRead(ORMModel):
    id: int
    fixture_id: int
    body: str
    author: str | None
    sent_at: datetime | None
    created_at: datetime
    added_by: str | None  # display name of the coach who pasted it
