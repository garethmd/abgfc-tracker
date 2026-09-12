import re

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import ClubTeam, Cohort, SquadMember, TeamSeason, UserRole
from app.repositories.club import ClubTeamRepository, CohortRepository, TeamSeasonRepository
from app.repositories.players import SquadRepository
from app.schemas.club import (
    ClubTeamCreate,
    ClubTeamUpdate,
    CohortCreate,
    CohortUpdate,
    TeamSeasonStart,
    TeamSeasonUpdate,
)
from app.services.access import Access
from app.services.seasons import SeasonService


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class CohortService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.repo = CohortRepository(db)

    def list_visible(self) -> list[Cohort]:
        return self.repo.list_all(ids=self.access.visible_cohort_ids())

    def get(self, id: int) -> Cohort:
        cohort = self.repo.get_or_404(id)
        self.access.require_cohort(id)
        return cohort

    def create(self, data: CohortCreate) -> Cohort:
        self.access.require_club(UserRole.ADMIN)
        if self.repo.get_by_name(data.name):
            raise ConflictError(f"Age group '{data.name}' already exists")
        cohort = self.repo.add(Cohort(**data.model_dump()))
        self.db.commit()
        return cohort

    def update(self, id: int, data: CohortUpdate) -> Cohort:
        self.access.require_club(UserRole.ADMIN)
        cohort = self.repo.get_or_404(id)
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(cohort, k, v)
        self.db.commit()
        return cohort


class ClubTeamService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.repo = ClubTeamRepository(db)

    def list_visible(self, cohort_id: int | None = None) -> list[ClubTeam]:
        return self.repo.list_all(ids=self.access.visible_team_ids(), cohort_id=cohort_id)

    def get(self, id: int) -> ClubTeam:
        team = self.repo.get_or_404(id)
        self.access.require_team(team)
        return team

    def get_by_slug(self, slug: str) -> ClubTeam:
        team = self.repo.get_by_slug(slug)
        if team is None:
            raise NotFoundError(f"Team '{slug}' not found")
        self.access.require_team(team)
        return team

    def create(self, data: ClubTeamCreate) -> ClubTeam:
        self.access.require_cohort(data.cohort_id, UserRole.ADMIN)
        CohortRepository(self.db).get_or_404(data.cohort_id)
        if data.slug:
            slug = data.slug
            if self.repo.get_by_slug(slug):
                raise ConflictError(f"A team with the URL name '{slug}' already exists")
        else:  # derive from the name; "blues" is taken by the other age group -> "blues-2"
            base = slugify(data.name)
            slug, n = base, 1
            while self.repo.get_by_slug(slug):
                n += 1
                slug = f"{base}-{n}"
        team = self.repo.add(ClubTeam(**data.model_dump(exclude={"slug"}), slug=slug))
        self.db.commit()
        return team

    def update(self, id: int, data: ClubTeamUpdate) -> ClubTeam:
        team = self.repo.get_or_404(id)
        self.access.require_team(team, UserRole.ADMIN)
        changes = data.model_dump(exclude_unset=True)
        if "slug" in changes:
            other = self.repo.get_by_slug(changes["slug"])
            if other and other.id != id:
                raise ConflictError(f"A team with the URL name '{changes['slug']}' already exists")
        for k, v in changes.items():
            setattr(team, k, v)
        self.db.commit()
        return team


class TeamSeasonService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.repo = TeamSeasonRepository(db)
        self.teams = ClubTeamRepository(db)

    def get(self, id: int, minimum: UserRole = UserRole.VIEWER) -> TeamSeason:
        ts = self.repo.get(id)
        if ts is None:
            raise NotFoundError(f"Team season {id} not found")
        self.access.require_team_season(ts, minimum)
        return ts

    def list_for_team(self, club_team_id: int) -> list[TeamSeason]:
        team = self.teams.get_or_404(club_team_id)
        self.access.require_team(team)
        return self.repo.list_for_team(club_team_id)

    def current_for_team(self, club_team_id: int) -> TeamSeason | None:
        team = self.teams.get_or_404(club_team_id)
        self.access.require_team(team)
        current = self.repo.get_current(club_team_id)
        if current is None:
            seasons = self.repo.list_for_team(club_team_id)
            current = seasons[0] if seasons else None
        return current

    def start(self, club_team_id: int, data: TeamSeasonStart) -> TeamSeason:
        """Roll a team into a season: create the season if needed, optionally copy the
        squad forward, and make it current."""
        team = self.teams.get_or_404(club_team_id)
        self.access.require_team(team, UserRole.COACH)
        seasons = SeasonService(self.db, self.access)
        season = (
            seasons.get(data.season_id)
            if data.season_id
            else seasons.get_or_create(data.season_name)
        )
        if self.repo.get_by_team_and_season(team.id, season.id):
            raise ConflictError(f"{team.name} already has a {season.name} season")

        ts = TeamSeason(
            club_team_id=team.id,
            season_id=season.id,
            age_group=data.age_group or team.cohort.age_group_for(season),
            format=data.format,
            match_minutes=data.match_minutes,
        )
        self.repo.add(ts)

        if data.copy_squad_from_team_season_id is not None:
            source = self.get(data.copy_squad_from_team_season_id)
            if (
                source.club_team_id != team.id
                and self.access.role_for_cohort(team.cohort_id) is None
            ):
                raise ValidationError("Can only copy a squad from your own team")
            for m in SquadRepository(self.db).list_for_team_season(source.id):
                if m.left_at is None and m.player.left_date is None:
                    self.db.add(
                        SquadMember(
                            team_season_id=ts.id,
                            player_id=m.player_id,
                            squad_number=m.squad_number,
                            primary_position_id=m.primary_position_id,
                        )
                    )
        if data.make_current:
            self.repo.set_current(ts)
        self.db.commit()
        return self.repo.get(ts.id)

    def update(self, id: int, data: TeamSeasonUpdate) -> TeamSeason:
        ts = self.get(id, UserRole.COACH)
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(ts, k, v)
        self.db.commit()
        return ts

    def make_current(self, id: int) -> TeamSeason:
        ts = self.get(id, UserRole.COACH)
        self.repo.set_current(ts)
        self.db.commit()
        return ts
