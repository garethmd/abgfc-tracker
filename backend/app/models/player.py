from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.club import Cohort, TeamSeason
    from app.models.lookup import Position
    from app.models.media import MediaLink


class Player(TimestampMixin, Base):
    """A person. Season membership lives in SquadMember. Never hard-deleted: set left_date."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The age group the child belongs to; squads are drawn from the cohort's players.
    cohort_id: Mapped[int | None] = mapped_column(
        ForeignKey("cohorts.id", ondelete="RESTRICT"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str | None] = mapped_column(String(50))
    display_name: Mapped[str] = mapped_column(String(50))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    joined_date: Mapped[date | None] = mapped_column(Date)
    left_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    cohort: Mapped["Cohort | None"] = relationship()
    squad_memberships: Mapped[list["SquadMember"]] = relationship(back_populates="player")
    profile_photo_link: Mapped["MediaLink | None"] = relationship(
        primaryjoin="and_(MediaLink.player_id == Player.id, MediaLink.role == 'profile_photo')",
        viewonly=True,
        uselist=False,
        lazy="selectin",
    )

    @property
    def photo_key(self) -> str | None:
        """Random token that changes with every upload; the client cache-busts with it."""
        link = self.profile_photo_link
        return link.media.storage_key.rsplit("/", 1)[-1] if link and link.media else None


class SquadMember(TimestampMixin, Base):
    """A player's membership of one team's squad for one season (number, primary position).
    Moving between teams mid-season = left_at here, a new row on the other team."""

    __tablename__ = "squad_members"
    __table_args__ = (
        UniqueConstraint("team_season_id", "player_id"),
        Index(
            "uq_squad_members_team_season_id_squad_number",
            "team_season_id",
            "squad_number",
            unique=True,
            sqlite_where=text("squad_number IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_season_id: Mapped[int] = mapped_column(ForeignKey("team_seasons.id", ondelete="RESTRICT"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"))
    squad_number: Mapped[int | None] = mapped_column(Integer)
    primary_position_id: Mapped[int | None] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT")
    )
    joined_at: Mapped[date | None] = mapped_column(Date)
    left_at: Mapped[date | None] = mapped_column(Date)

    team_season: Mapped["TeamSeason"] = relationship(back_populates="squad_members")
    player: Mapped["Player"] = relationship(back_populates="squad_memberships")
    primary_position: Mapped["Position | None"] = relationship()
