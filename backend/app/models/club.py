from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.fixture import Fixture
    from app.models.player import SquadMember
    from app.models.season import Season


class Cohort(TimestampMixin, Base):
    """An age group, independent of season: the children born Sept 2016-Aug 2017 are
    U10 this season and U11 next. Teams belong to a cohort; so does the age-group coach."""

    __tablename__ = "cohorts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    birth_year_start: Mapped[int | None] = mapped_column(Integer)  # school year starting Sept
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    teams: Mapped[list["ClubTeam"]] = relationship(
        back_populates="cohort", order_by="ClubTeam.sort_order"
    )

    def age_group_for(self, season: "Season") -> str | None:
        """'U10' for a 2026/27 season and a 2016 cohort."""
        if self.birth_year_start is None or season.start_date is None:
            return None
        return f"U{season.start_date.year - self.birth_year_start}"


class ClubTeam(TimestampMixin, Base):
    """One of our teams (Blues, Blacks, Reds, Whites). Not the same as `teams`, which is
    opposition; a club team can link to its opposition row for derbies."""

    __tablename__ = "club_teams"
    __table_args__ = (UniqueConstraint("cohort_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("cohorts.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(50))
    slug: Mapped[str] = mapped_column(String(50), unique=True)  # used in URLs: /blues/...
    colour: Mapped[str | None] = mapped_column(String(30))  # CSS colour for the accent
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    cohort: Mapped[Cohort] = relationship(back_populates="teams")
    team_seasons: Mapped[list["TeamSeason"]] = relationship(back_populates="club_team")


class TeamSeason(TimestampMixin, Base):
    """A club team's participation in a season. Squad, fixtures, awards and stats all
    hang off this - it's what a coach is looking at."""

    __tablename__ = "team_seasons"
    __table_args__ = (UniqueConstraint("club_team_id", "season_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    club_team_id: Mapped[int] = mapped_column(ForeignKey("club_teams.id", ondelete="RESTRICT"))
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))
    age_group: Mapped[str | None] = mapped_column(String(10))  # "U10"
    format: Mapped[str | None] = mapped_column(String(10))  # "7v7"
    # Default match length; FA U10 maximum is 50 minutes, U11 is 60.
    match_minutes: Mapped[int] = mapped_column(Integer, default=50, server_default="50")
    # One current team-season per club team; enforced in the service layer.
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # "Please arrive at ..." in the parents' message = kick-off minus this.
    arrival_lead_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30")

    club_team: Mapped[ClubTeam] = relationship(back_populates="team_seasons")
    season: Mapped["Season"] = relationship(back_populates="team_seasons")
    squad_members: Mapped[list["SquadMember"]] = relationship(back_populates="team_season")
    fixtures: Mapped[list["Fixture"]] = relationship(back_populates="team_season")
