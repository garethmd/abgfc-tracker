from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import SelectionStatus, check_in

if TYPE_CHECKING:
    from app.models.fixture import Fixture
    from app.models.player import Player
    from app.models.user import User


class FixtureSelection(TimestampMixin, Base):
    """The coach's plan for an upcoming match: who starts, who's a sub, who's out, plus
    the bits parents need to know. A plan, not a record - appearances (who actually
    played) are only ever written by the result flows. One per fixture; goes with it."""

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
    players: Mapped[list["SelectionPlayer"]] = relationship(
        back_populates="selection", cascade="all, delete-orphan", order_by="SelectionPlayer.id"
    )


class SelectionPlayer(Base):
    """One player's place in the plan. `start` and `sub` together are the squad the
    parents' message lists; the live-match line-up reads the same split."""

    __tablename__ = "fixture_selection_players"
    __table_args__ = (
        UniqueConstraint("selection_id", "player_id"),
        CheckConstraint(check_in("status", SelectionStatus), name="status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("fixture_selections.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))
    status: Mapped[SelectionStatus] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(100))  # "injured", "away"

    selection: Mapped[FixtureSelection] = relationship(back_populates="players")
    player: Mapped["Player"] = relationship()
