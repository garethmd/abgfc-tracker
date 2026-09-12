from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Team(TimestampMixin, Base):
    """Opposition teams. Fixtures are always us-vs-opposition. When the opposition is
    another of our own teams (a derby), club_team_id links the two."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("club_teams.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(100), unique=True)
    short_name: Mapped[str | None] = mapped_column(String(30))
    colours: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
