from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.fixture import Fixture
    from app.models.user import User


class MatchNote(TimestampMixin, Base):
    """A free-text report attached to a fixture - typically a message pasted from the
    parents' WhatsApp group. Several per match; `author`/`sent_at` describe the original
    message, `created_by` is the coach who pasted it."""

    __tablename__ = "match_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(100))  # who wrote the message
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)  # when it was sent
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    fixture: Mapped["Fixture"] = relationship(back_populates="match_notes")
    created_by: Mapped["User | None"] = relationship()
