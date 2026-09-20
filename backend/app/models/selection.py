from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.fixture import Fixture
    from app.models.player import Player
    from app.models.user import User


class FixtureSelection(TimestampMixin, Base):
    """Availability for an upcoming match: everyone in the squad is assumed available
    unless listed in `unavailable`, plus the bits parents need to know. A plan, not a
    record - appearances (who actually played) are only ever written by the result
    flows. One per fixture; goes with it."""

    __tablename__ = "fixture_selections"

    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), unique=True
    )
    coaching: Mapped[str | None] = mapped_column(String(200))  # "Adam & Dan"
    notes: Mapped[str | None] = mapped_column(Text)  # free text for parents
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    fixture: Mapped["Fixture"] = relationship(back_populates="selection")
    created_by: Mapped["User | None"] = relationship()
    unavailable: Mapped[list["UnavailablePlayer"]] = relationship(
        back_populates="selection", cascade="all, delete-orphan", order_by="UnavailablePlayer.id"
    )


class UnavailablePlayer(Base):
    """A player the coach has marked as not available for this match. Everyone else in
    the squad is available - that is the squad the parents' message lists."""

    __tablename__ = "fixture_unavailable_players"
    __table_args__ = (UniqueConstraint("selection_id", "player_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("fixture_selections.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))

    selection: Mapped[FixtureSelection] = relationship(back_populates="unavailable")
    player: Mapped["Player"] = relationship()
