from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models import Season, UserRole
from app.repositories.club import TeamSeasonRepository
from app.repositories.seasons import SeasonRepository
from app.schemas.season import SeasonCreate, SeasonUpdate
from app.services.access import Access


class SeasonService:
    """Club-wide seasons. Anyone signed in can see them; creating one is harmless
    (it's a name), so coaches may do it when starting their team's season."""

    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.repo = SeasonRepository(db)

    def list_all(self) -> list[Season]:
        return self.repo.list_all()

    def get(self, id: int) -> Season:
        return self.repo.get_or_404(id)

    def create(self, data: SeasonCreate) -> Season:
        if self.repo.get_by_name(data.name):
            raise ConflictError(f"Season '{data.name}' already exists")
        season = self.repo.add(Season(**data.model_dump()))
        self.db.commit()
        return season

    def get_or_create(self, name: str) -> Season:
        season = self.repo.get_by_name(name)
        if season is None:
            season = self.repo.add(Season(name=name, **_dates_for(name)))
        return season

    def update(self, id: int, data: SeasonUpdate) -> Season:
        self.access.require_club(UserRole.ADMIN)
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

    def delete(self, id: int) -> None:
        self.access.require_club(UserRole.ADMIN)
        season = self.repo.get_or_404(id)
        if TeamSeasonRepository(self.db).list_for_season(id):
            raise ConflictError("Season is in use by a team; remove those first")
        self.repo.delete(season)
        self.db.commit()


def _dates_for(name: str) -> dict:
    """'2027/28' -> Sept 1 2027 to May 31 2028; anything else -> no dates."""
    from datetime import date

    try:
        start = int(name.split("/")[0])
        return {"start_date": date(start, 9, 1), "end_date": date(start + 1, 5, 31)}
    except (ValueError, IndexError):
        return {}
