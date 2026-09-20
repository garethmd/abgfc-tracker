from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import FixtureStatus, Venue, check_in

if TYPE_CHECKING:
    from app.models.award import Award
    from app.models.club import TeamSeason
    from app.models.lookup import Competition
    from app.models.match import Appearance, MatchEvent
    from app.models.note import MatchNote
    from app.models.selection import FixtureSelection
    from app.models.team import Team


class Fixture(TimestampMixin, Base):
    __tablename__ = "fixtures"
    __table_args__ = (
        UniqueConstraint("team_season_id", "match_number"),
        CheckConstraint(check_in("venue", Venue), name="venue"),
        CheckConstraint(check_in("status", FixtureStatus), name="status"),
        CheckConstraint("our_score IS NULL OR our_score >= 0", name="our_score_nonneg"),
        CheckConstraint("their_score IS NULL OR their_score >= 0", name="their_score_nonneg"),
        Index("ix_fixtures_team_season_id_kickoff_at", "team_season_id", "kickoff_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_season_id: Mapped[int] = mapped_column(ForeignKey("team_seasons.id", ondelete="RESTRICT"))
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id", ondelete="RESTRICT"))
    opposition_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    match_number: Mapped[int | None] = mapped_column(Integer)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime)
    venue: Mapped[Venue] = mapped_column(String(10), default=Venue.HOME)
    venue_notes: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[FixtureStatus] = mapped_column(String(20), default=FixtureStatus.SCHEDULED)
    # Stored, not derived: at pitchside you often know the score before the scorers.
    # The service layer warns when goal events disagree with these.
    our_score: Mapped[int | None] = mapped_column(Integer)
    their_score: Mapped[int | None] = mapped_column(Integer)
    duration_minutes: Mapped[int | None] = mapped_column(
        Integer
    )  # overrides team_season.match_minutes
    notes: Mapped[str | None] = mapped_column(Text)
    # The FA Full-Time fixture id when imported from there; lets re-imports update, not duplicate.
    external_id: Mapped[str | None] = mapped_column(String(50), unique=True)

    team_season: Mapped["TeamSeason"] = relationship(back_populates="fixtures")
    competition: Mapped["Competition"] = relationship()
    opposition: Mapped["Team"] = relationship()
    appearances: Mapped[list["Appearance"]] = relationship(
        back_populates="fixture", cascade="all, delete-orphan", order_by="Appearance.id"
    )
    events: Mapped[list["MatchEvent"]] = relationship(
        back_populates="fixture", cascade="all, delete-orphan", order_by="MatchEvent.sequence"
    )
    awards: Mapped[list["Award"]] = relationship(
        back_populates="fixture", cascade="all, delete-orphan"
    )
    match_notes: Mapped[list["MatchNote"]] = relationship(
        back_populates="fixture", cascade="all, delete-orphan", order_by="MatchNote.sent_at"
    )
    # The pre-match plan (services/selections.py); None until a coach picks a squad.
    selection: Mapped["FixtureSelection | None"] = relationship(
        back_populates="fixture", cascade="all, delete-orphan", uselist=False
    )

    @property
    def effective_duration(self) -> int:
        return self.duration_minutes or self.team_season.match_minutes
