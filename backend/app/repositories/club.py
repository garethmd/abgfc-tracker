from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models import ClubTeam, Cohort, TeamSeason
from app.repositories.base import BaseRepository


class CohortRepository(BaseRepository[Cohort]):
    model = Cohort
    label = "Age group"

    def list_all(self, ids: set[int] | None = None) -> list[Cohort]:
        stmt = select(Cohort).order_by(Cohort.birth_year_start.desc().nulls_last(), Cohort.name)
        if ids is not None:
            stmt = stmt.where(Cohort.id.in_(ids))
        return list(self.db.scalars(stmt))

    def get_by_name(self, name: str) -> Cohort | None:
        return self.db.scalar(select(Cohort).where(Cohort.name == name))


class ClubTeamRepository(BaseRepository[ClubTeam]):
    model = ClubTeam
    label = "Team"

    def list_all(self, ids: set[int] | None = None, cohort_id: int | None = None) -> list[ClubTeam]:
        stmt = (
            select(ClubTeam)
            .options(selectinload(ClubTeam.cohort))
            .order_by(ClubTeam.sort_order, ClubTeam.name)
        )
        if ids is not None:
            stmt = stmt.where(ClubTeam.id.in_(ids))
        if cohort_id is not None:
            stmt = stmt.where(ClubTeam.cohort_id == cohort_id)
        return list(self.db.scalars(stmt))

    def get_by_slug(self, slug: str) -> ClubTeam | None:
        return self.db.scalar(select(ClubTeam).where(ClubTeam.slug == slug))


class TeamSeasonRepository(BaseRepository[TeamSeason]):
    model = TeamSeason
    label = "Team season"

    _options = (selectinload(TeamSeason.club_team), selectinload(TeamSeason.season))

    def get(self, id: int) -> TeamSeason | None:
        return self.db.scalar(select(TeamSeason).where(TeamSeason.id == id).options(*self._options))

    def list_for_team(self, club_team_id: int) -> list[TeamSeason]:
        from app.models import Season

        stmt = (
            select(TeamSeason)
            .join(TeamSeason.season)
            .where(TeamSeason.club_team_id == club_team_id)
            .options(*self._options)
            .order_by(Season.start_date.desc().nulls_last(), Season.name.desc())
        )
        return list(self.db.scalars(stmt))

    def list_for_season(self, season_id: int, team_ids: set[int] | None = None) -> list[TeamSeason]:
        stmt = select(TeamSeason).where(TeamSeason.season_id == season_id).options(*self._options)
        if team_ids is not None:
            stmt = stmt.where(TeamSeason.club_team_id.in_(team_ids))
        return list(self.db.scalars(stmt))

    def get_current(self, club_team_id: int) -> TeamSeason | None:
        stmt = (
            select(TeamSeason)
            .where(TeamSeason.club_team_id == club_team_id, TeamSeason.is_current.is_(True))
            .options(*self._options)
        )
        return self.db.scalar(stmt)

    def get_by_team_and_season(self, club_team_id: int, season_id: int) -> TeamSeason | None:
        return self.db.scalar(
            select(TeamSeason).where(
                TeamSeason.club_team_id == club_team_id, TeamSeason.season_id == season_id
            )
        )

    def set_current(self, ts: TeamSeason) -> None:
        self.db.execute(
            update(TeamSeason)
            .where(TeamSeason.club_team_id == ts.club_team_id)
            .values(is_current=False)
        )
        ts.is_current = True
        self.db.flush()
