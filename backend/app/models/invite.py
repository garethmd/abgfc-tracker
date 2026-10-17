from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import TokenPurpose, check_in

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.user import User


class LoginToken(TimestampMixin, Base):
    """A single-use link emailed to a parent: either an invitation to join (no account
    yet) or a sign-in link for an account that exists. Parents never have a password, so
    this is the whole of their authentication.

    Only the SHA-256 hash is stored - the raw token exists in the email and nowhere else.
    A fast hash is right here (unlike passwords): the token is 256 bits of CSPRNG output,
    so there is nothing to brute-force, and the lookup needs an index.
    """

    __tablename__ = "login_tokens"
    __table_args__ = (
        CheckConstraint(check_in("purpose", TokenPurpose), name="purpose"),
        CheckConstraint(
            "(purpose = 'invite' AND player_id IS NOT NULL AND user_id IS NULL) "
            "OR (purpose IN ('signin', 'reset') AND user_id IS NOT NULL)",
            name="purpose_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[TokenPurpose] = mapped_column(String(20))
    # NULL when the coach is sending the link by hand (WhatsApp): the parent gives
    # their address when they accept, and that is what the account is keyed on.
    email: Mapped[str | None] = mapped_column(String(255))  # lowercased
    # invite: the child this parent belongs to (their cohort decides what they can see)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    # signin: the account the link signs into
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    player: Mapped["Player | None"] = relationship()
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])
    invited_by: Mapped["User | None"] = relationship(foreign_keys=[invited_by_user_id])

    @property
    def is_live(self) -> bool:
        return self.used_at is None and self.revoked_at is None and self.expires_at > _now()


def _now() -> datetime:
    return datetime.now()
