from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models import AwardType, Competition, Team, UserRole
from app.repositories.club import ClubTeamRepository
from app.repositories.fixtures import FixtureRepository
from app.repositories.lookups import AwardTypeRepository, CompetitionRepository
from app.repositories.teams import TeamRepository
from app.schemas.lookup import (
    AwardTypeCreate,
    AwardTypeUpdate,
    CompetitionCreate,
    CompetitionUpdate,
)
from app.schemas.team import HeadToHead, HeadToHeadFixture, TeamCreate, TeamUpdate
from app.services.access import Access
from app.services.club import slugify


class CompetitionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CompetitionRepository(db)

    def list_all(self) -> list[Competition]:
        return self.repo.list_all()

    def create(self, data: CompetitionCreate) -> Competition:
        if self.repo.get_by_name(data.name):
            raise ConflictError(f"Competition '{data.name}' already exists")
        comp = self.repo.add(Competition(**data.model_dump()))
        self.db.commit()
        return comp

    def update(self, id: int, data: CompetitionUpdate) -> Competition:
        comp = self.repo.get_or_404(id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            other = self.repo.get_by_name(changes["name"])
            if other and other.id != id:
                raise ConflictError(f"Competition '{changes['name']}' already exists")
        for k, v in changes.items():
            setattr(comp, k, v)
        self.db.commit()
        return comp

    def delete(self, id: int) -> None:
        comp = self.repo.get_or_404(id)
        if FixtureRepository(self.db).list_all(competition_id=id):
            raise ConflictError("Competition has fixtures; mark it inactive instead")
        self.repo.delete(comp)
        self.db.commit()


class TeamService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TeamRepository(db)

    def list_all(self) -> list[Team]:
        return self.repo.list_all()

    def get(self, id: int) -> Team:
        return self.repo.get_or_404(id)

    def create(self, data: TeamCreate) -> Team:
        if self.repo.get_by_name(data.name):
            raise ConflictError(f"Team '{data.name}' already exists")
        team = self.repo.add(Team(**data.model_dump()))
        self.db.commit()
        return team

    def update(self, id: int, data: TeamUpdate) -> Team:
        team = self.repo.get_or_404(id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            other = self.repo.get_by_name(changes["name"])
            if other and other.id != id:
                raise ConflictError(f"Team '{changes['name']}' already exists")
        for k, v in changes.items():
            setattr(team, k, v)
        self.db.commit()
        return team

    def head_to_head(self, id: int, access: Access, club_team_id: int | None) -> HeadToHead:
        """Our record against this opposition: every fixture the caller can see, or just
        one of our teams' when club_team_id is given."""
        from app.models import FixtureStatus
        from app.services.stats import form, outcome, team_record

        team = self.repo.get_or_404(id)
        if club_team_id is not None:
            access.require_team(ClubTeamRepository(self.db).get_or_404(club_team_id))
        fixtures = FixtureRepository(self.db).list_v_opposition(
            id, access.visible_team_ids(), club_team_id
        )

        def item(f) -> HeadToHeadFixture:
            played = f.status == FixtureStatus.PLAYED and f.our_score is not None
            return HeadToHeadFixture(
                id=f.id,
                team_season_id=f.team_season_id,
                club_team_id=f.team_season.club_team_id,
                club_team_name=f.team_season.club_team.name,
                season_name=f.team_season.season.name,
                competition_name=f.competition.name,
                match_number=f.match_number,
                kickoff_at=f.kickoff_at,
                venue=f.venue,
                venue_notes=f.venue_notes,
                status=f.status,
                our_score=f.our_score,
                their_score=f.their_score,
                result=outcome(f.our_score, f.their_score) if played else None,
            )

        played = [f for f in fixtures if f.status == FixtureStatus.PLAYED]
        upcoming = [f for f in fixtures if f.status == FixtureStatus.SCHEDULED]
        other = [f for f in fixtures if f not in played and f not in upcoming]
        return HeadToHead(
            team=team,
            record=team_record(played),
            form=[x.result for x in form(played, n=len(played) or 1)],
            played=[item(f) for f in reversed(played)],
            upcoming=[item(f) for f in upcoming],
            other=[item(f) for f in other],
        )

    def delete(self, id: int) -> None:
        team = self.repo.get_or_404(id)
        from sqlalchemy import select

        from app.models import Fixture

        if self.db.scalar(select(Fixture.id).where(Fixture.opposition_team_id == id).limit(1)):
            raise ConflictError("Team has fixtures and cannot be deleted")
        self.repo.delete(team)
        self.db.commit()


class AwardTypeService:
    """Club-wide award types (both POTMs) plus per-team ones ("Blues most improved")."""

    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.repo = AwardTypeRepository(db)

    def list_for_team(self, club_team_id: int | None, active_only: bool = True) -> list[AwardType]:
        if club_team_id is not None:
            self.access.require_team(ClubTeamRepository(self.db).get_or_404(club_team_id))
            return self.repo.list_all(active_only=active_only, club_team_id=club_team_id)
        types = self.repo.list_all(active_only=active_only)
        visible = self.access.visible_team_ids()
        return [
            t
            for t in types
            if t.club_team_id is None or visible is None or t.club_team_id in visible
        ]

    def create(self, data: AwardTypeCreate) -> AwardType:
        if data.club_team_id is None:
            self.access.require_club(UserRole.ADMIN)
            code = slugify(data.name).replace("-", "_")
        else:
            team = ClubTeamRepository(self.db).get_or_404(data.club_team_id)
            self.access.require_team(team, UserRole.COACH)
            code = f"{team.slug}_{slugify(data.name)}".replace("-", "_")
        if self.repo.get_by_code(code):
            raise ConflictError(f"Award '{data.name}' already exists")
        existing = self.repo.list_all()
        award = self.repo.add(
            AwardType(
                code=code,
                name=data.name,
                scope=data.scope,
                club_team_id=data.club_team_id,
                sort_order=max((a.sort_order for a in existing), default=-1) + 1,
            )
        )
        self.db.commit()
        return award

    def update(self, id: int, data: AwardTypeUpdate) -> AwardType:
        award = self.repo.get_or_404(id)
        if award.club_team_id is None:
            self.access.require_club(UserRole.ADMIN)
        else:
            self.access.require_team(
                ClubTeamRepository(self.db).get_or_404(award.club_team_id), UserRole.COACH
            )
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(award, k, v)
        self.db.commit()
        return award
