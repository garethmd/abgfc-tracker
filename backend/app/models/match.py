from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import EventType, check_in

if TYPE_CHECKING:
    from app.models.fixture import Fixture
    from app.models.lookup import Position
    from app.models.player import Player


class Appearance(TimestampMixin, Base):
    """One row per player per fixture. Minutes come from PlayerStint rows, when recorded."""

    __tablename__ = "appearances"
    __table_args__ = (UniqueConstraint("fixture_id", "player_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), index=True
    )
    started: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="RESTRICT"))
    shirt_number: Mapped[int | None] = mapped_column(Integer)
    captain: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    fixture: Mapped["Fixture"] = relationship(back_populates="appearances")
    player: Mapped["Player"] = relationship()
    position: Mapped["Position | None"] = relationship()
    stints: Mapped[list["PlayerStint"]] = relationship(
        back_populates="appearance", cascade="all, delete-orphan", order_by="PlayerStint.on_minute"
    )


class PlayerStint(Base):
    """A continuous spell on the pitch. Hangs off the appearance so a stint can't exist
    for someone who didn't play. off_minute NULL = on until the final whistle."""

    __tablename__ = "player_stints"
    __table_args__ = (
        CheckConstraint("off_minute IS NULL OR off_minute > on_minute", name="off_after_on"),
        CheckConstraint("on_minute >= 0", name="on_minute_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    appearance_id: Mapped[int] = mapped_column(
        ForeignKey("appearances.id", ondelete="CASCADE"), index=True
    )
    on_minute: Mapped[int] = mapped_column(Integer)
    off_minute: Mapped[int | None] = mapped_column(Integer)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id", ondelete="RESTRICT"))

    appearance: Mapped[Appearance] = relationship(back_populates="stints")
    position: Mapped["Position | None"] = relationship()


class MatchEvent(TimestampMixin, Base):
    """Goals, assists, own goals. Goals and assists are derived by counting these."""

    __tablename__ = "match_events"
    __table_args__ = (
        CheckConstraint(check_in("event_type", EventType), name="event_type"),
        # Only an opposition own goal has no player.
        CheckConstraint(
            "(event_type = 'opp_own_goal' AND player_id IS NULL) "
            "OR (event_type <> 'opp_own_goal' AND player_id IS NOT NULL)",
            name="player_required",
        ),
        Index("ix_match_events_fixture_id_sequence", "fixture_id", "sequence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"))
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[EventType] = mapped_column(String(20))
    minute: Mapped[int | None] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(Integer, default=0)  # ordering when minute unknown
    related_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("match_events.id", ondelete="CASCADE"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    fixture: Mapped["Fixture"] = relationship(back_populates="events")
    player: Mapped["Player | None"] = relationship()
    related_event: Mapped["MatchEvent | None"] = relationship(remote_side=[id])
