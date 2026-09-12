from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.club import TeamSeason


class Season(TimestampMixin, Base):
    """Club-wide: "2026/27". Per-team detail (age group, match length) is on TeamSeason."""

    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    team_seasons: Mapped[list["TeamSeason"]] = relationship(back_populates="season")
