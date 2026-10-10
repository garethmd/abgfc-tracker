from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import InputModel, ORMModel
from app.schemas.player import PlayerSummary

# Deliberately loose: a real address is proved by the link arriving, not by a regex.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s.]+\.[^@\s]+$"


class _WithEmail(InputModel):
    email: str = Field(min_length=3, max_length=255, pattern=EMAIL_PATTERN)

    @field_validator("email")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return v.strip().lower()


class InviteCreate(_WithEmail):
    """Invite one parent to see the club, as the guardian of one child."""

    player_id: int


class InviteRead(ORMModel):
    id: int
    email: str
    player: PlayerSummary
    invited_by: str | None
    expires_at: datetime
    created_at: datetime


class InviteCreated(InviteRead):
    """The link is returned **once**, when the invite is made, so the coach can send it
    by hand if email is slow, bounces, or the parent only uses WhatsApp. It is not
    stored and never appears in a listing."""

    link: str
    emailed: bool
    share_text: str  # the note to send the parent, link included


class InvitePreview(ORMModel):
    """What the landing page shows before the parent commits - no account exists yet."""

    player_name: str
    team_names: list[str]
    invited_by: str | None
    email: str


class InviteAccept(InputModel):
    display_name: str = Field(min_length=1, max_length=100)


class SigninLinkRequest(_WithEmail):
    pass


class GuardianRead(ORMModel):
    id: int
    user_id: int
    display_name: str | None
    email: str | None
    is_active: bool
    last_signed_in: datetime | None


class PlayerAccessRead(ORMModel):
    """One child and who can see the club because of them - the Parents tab."""

    player: PlayerSummary
    guardians: list[GuardianRead]
    pending: list[InviteRead]


class LeaverRead(ORMModel):
    """A parent account whose children have all left the club. Access doesn't lapse on
    its own, so these are listed for a coach to close."""

    user_id: int
    display_name: str | None
    email: str | None
    is_active: bool
    children: list[str]


class TeamParentsRead(ORMModel):
    players: list[PlayerAccessRead]
    leavers: list[LeaverRead]
