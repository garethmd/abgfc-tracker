from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.lookup import Position
    from app.models.season import Season


class Player(TimestampMixin, Base):
    """A person. Season membership lives in SquadMember. Never hard-deleted: set left_date."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str | None] = mapped_column(String(50))
    display_name: Mapped[str] = mapped_column(String(50))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    joined_date: Mapped[date | None] = mapped_column(Date)
    left_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    squad_memberships: Mapped[list["SquadMember"]] = relationship(back_populates="player")


class SquadMember(TimestampMixin, Base):
    """A player's membership of one season's squad (number, primary position)."""

    __tablename__ = "squad_members"
    __table_args__ = (
        UniqueConstraint("season_id", "player_id"),
        Index(
            "uq_squad_members_season_id_squad_number",
            "season_id",
            "squad_number",
            unique=True,
            sqlite_where=text("squad_number IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))
    squad_number: Mapped[int | None] = mapped_column(Integer)
    primary_position_id: Mapped[int | None] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT")
    )
    joined_at: Mapped[date | None] = mapped_column(Date)
    left_at: Mapped[date | None] = mapped_column(Date)

    season: Mapped["Season"] = relationship(back_populates="squad_members")
    player: Mapped["Player"] = relationship(back_populates="squad_memberships")
    primary_position: Mapped["Position | None"] = relationship()
