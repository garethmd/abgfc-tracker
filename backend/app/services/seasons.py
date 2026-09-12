from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Season
from app.repositories.fixtures import FixtureRepository
from app.repositories.seasons import SeasonRepository
from app.schemas.season import SeasonCreate, SeasonUpdate


class SeasonService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SeasonRepository(db)

    def list_all(self) -> list[Season]:
        return self.repo.list_all()

    def get(self, id: int) -> Season:
        return self.repo.get_or_404(id)

    def current(self) -> Season:
        season = self.repo.get_current()
        if season is None:
            raise NotFoundError("No current season - create one first")
        return season

    def create(self, data: SeasonCreate) -> Season:
        if self.repo.get_by_name(data.name):
            raise ConflictError(f"Season '{data.name}' already exists")
        make_current = data.is_current or self.repo.get_current() is None
        season = Season(**data.model_dump(exclude={"is_current"}))
        self.repo.add(season)
        if make_current:
            self.repo.set_current(season)
        self.db.commit()
        return season

    def update(self, id: int, data: SeasonUpdate) -> Season:
        season = self.repo.get_or_404(id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            other = self.repo.get_by_name(changes["name"])
            if other and other.id != id:
                raise ConflictError(f"Season '{changes['name']}' already exists")
        for k, v in changes.items():
            setattr(season, k, v)
        self.db.commit()
        return season

    def make_current(self, id: int) -> Season:
        season = self.repo.get_or_404(id)
        self.repo.set_current(season)
        self.db.commit()
        return season

    def delete(self, id: int) -> None:
        season = self.repo.get_or_404(id)
        if FixtureRepository(self.db).list_all(season_id=id):
            raise ConflictError("Season has fixtures; delete those first")
        if season.squad_members:
            raise ConflictError("Season has squad members; remove them first")
        self.repo.delete(season)
        self.db.commit()
