from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models import Competition, Team
from app.repositories.fixtures import FixtureRepository
from app.repositories.lookups import CompetitionRepository
from app.repositories.teams import TeamRepository
from app.schemas.lookup import CompetitionCreate, CompetitionUpdate
from app.schemas.team import TeamCreate, TeamUpdate


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

    def delete(self, id: int) -> None:
        team = self.repo.get_or_404(id)
        from sqlalchemy import select

        from app.models import Fixture

        if self.db.scalar(select(Fixture.id).where(Fixture.opposition_team_id == id).limit(1)):
            raise ConflictError("Team has fixtures and cannot be deleted")
        self.repo.delete(team)
        self.db.commit()
