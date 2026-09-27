from pydantic import Field

from app.schemas.common import InputModel, ORMModel


class FixtureVideoCreate(InputModel):
    """A YouTube link pasted from the phone's share sheet, in whatever form it takes."""

    url: str = Field(min_length=1, max_length=500, examples=["https://youtu.be/dQw4w9WgXcQ"])
    title: str | None = Field(default=None, max_length=200, examples=["Second half"])


class FixtureVideoUpdate(InputModel):
    url: str | None = Field(default=None, min_length=1, max_length=500)
    title: str | None = Field(default=None, max_length=200)
    sort_order: int | None = Field(default=None, ge=0)


class FixtureVideoRead(ORMModel):
    id: int  # the media id
    fixture_id: int
    video_id: str  # the 11-character YouTube id; the player is built from this
    url: str  # canonical watch URL, for "open on YouTube"
    title: str | None
    sort_order: int
