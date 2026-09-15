from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models import (
    Appearance,
    Award,
    Competition,
    Fixture,
    FixtureStatus,
    MatchEvent,
    MatchNote,
    TeamSeason,
)
from app.repositories.base import BaseRepository


class FixtureRepository(BaseRepository[Fixture]):
    model = Fixture
    label = "Fixture"

    _list_options = (
        selectinload(Fixture.competition),
        selectinload(Fixture.opposition),
        selectinload(Fixture.team_season).selectinload(TeamSeason.club_team),
    )

    def list_all(
        self,
        team_season_id: int | None = None,
        team_ids: set[int] | None = None,
        competition_id: int | None = None,
        status: FixtureStatus | None = None,
    ) -> list[Fixture]:
        stmt = select(Fixture).options(*self._list_options).order_by(Fixture.kickoff_at, Fixture.id)
        if team_season_id is not None:
            stmt = stmt.where(Fixture.team_season_id == team_season_id)
        if team_ids is not None:
            stmt = stmt.join(Fixture.team_season).where(TeamSeason.club_team_id.in_(team_ids))
        if competition_id is not None:
            stmt = stmt.where(Fixture.competition_id == competition_id)
        if status is not None:
            stmt = stmt.where(Fixture.status == status)
        return list(self.db.scalars(stmt))

    def get_detail(self, id: int) -> Fixture | None:
        stmt = (
            select(Fixture)
            .where(Fixture.id == id)
            .options(
                *self._list_options,
                selectinload(Fixture.appearances).selectinload(Appearance.player),
                selectinload(Fixture.appearances).selectinload(Appearance.position),
                selectinload(Fixture.events).selectinload(MatchEvent.player),
                selectinload(Fixture.awards).selectinload(Award.player),
                selectinload(Fixture.awards).selectinload(Award.award_type),
                selectinload(Fixture.match_notes).selectinload(MatchNote.created_by),
            )
        )
        return self.db.scalar(stmt)

    def list_played(self, team_season_id: int) -> list[Fixture]:
        """Played fixtures with competition loaded - the input to team-record stats."""
        stmt = (
            select(Fixture)
            .where(Fixture.team_season_id == team_season_id, Fixture.status == FixtureStatus.PLAYED)
            .options(*self._list_options)
            .order_by(Fixture.kickoff_at, Fixture.id)
        )
        return list(self.db.scalars(stmt))

    def played_fixture_ids(
        self, team_season_id: int, competition_type: str | None = None
    ) -> list[int]:
        stmt = select(Fixture.id).where(
            Fixture.team_season_id == team_season_id, Fixture.status == FixtureStatus.PLAYED
        )
        if competition_type is not None:
            stmt = stmt.join(Fixture.competition).where(Competition.type == competition_type)
        return list(self.db.scalars(stmt))

    def next_match_number(self, team_season_id: int) -> int:
        current = self.db.scalar(
            select(func.max(Fixture.match_number)).where(Fixture.team_season_id == team_season_id)
        )
        return (current or 0) + 1
