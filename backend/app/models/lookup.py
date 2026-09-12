from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AwardScope, CompetitionType, PositionCategory, check_in


class Position(Base):
    """GK/DEF/MID/FWD today; finer positions later are rows sharing a category."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    category: Mapped[PositionCategory] = mapped_column(
        String(10), CheckConstraint(check_in("category", PositionCategory), name="category")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[CompetitionType] = mapped_column(
        String(20), CheckConstraint(check_in("type", CompetitionType), name="type")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class AwardType(Base):
    """Adding a third award is a row here, not a migration.
    club_team_id NULL = club-wide (both POTMs); set = only that team uses it."""

    __tablename__ = "award_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("club_teams.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    scope: Mapped[AwardScope] = mapped_column(
        String(20), CheckConstraint(check_in("scope", AwardScope), name="scope")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
