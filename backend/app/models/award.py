from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.fixture import Fixture
    from app.models.lookup import AwardType
    from app.models.player import Player


class Award(TimestampMixin, Base):
    """Joint winners are allowed: uniqueness includes player_id."""

    __tablename__ = "awards"
    __table_args__ = (
        UniqueConstraint("award_type_id", "fixture_id", "player_id"),
        Index("ix_awards_team_season_id_award_type_id", "team_season_id", "award_type_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    award_type_id: Mapped[int] = mapped_column(ForeignKey("award_types.id", ondelete="RESTRICT"))
    team_season_id: Mapped[int] = mapped_column(ForeignKey("team_seasons.id", ondelete="RESTRICT"))
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), index=True
    )
    fixture_id: Mapped[int | None] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"))
    period_label: Mapped[str | None] = mapped_column(String(50))  # e.g. "September"
    notes: Mapped[str | None] = mapped_column(Text)

    award_type: Mapped["AwardType"] = relationship()
    player: Mapped["Player"] = relationship()
    fixture: Mapped["Fixture | None"] = relationship(back_populates="awards")
