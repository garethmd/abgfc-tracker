from sqlalchemy import select

from app.models import AwardType, Competition, Position
from app.repositories.base import BaseRepository


class PositionRepository(BaseRepository[Position]):
    model = Position
    label = "Position"

    def list_all(self) -> list[Position]:
        return list(self.db.scalars(select(Position).order_by(Position.sort_order, Position.id)))


class CompetitionRepository(BaseRepository[Competition]):
    model = Competition
    label = "Competition"

    def get_by_name(self, name: str) -> Competition | None:
        return self.db.scalar(select(Competition).where(Competition.name == name))

    def list_all(self) -> list[Competition]:
        return list(self.db.scalars(select(Competition).order_by(Competition.name)))


class AwardTypeRepository(BaseRepository[AwardType]):
    model = AwardType
    label = "Award type"

    def list_all(self, active_only: bool = False) -> list[AwardType]:
        stmt = select(AwardType).order_by(AwardType.sort_order, AwardType.id)
        if active_only:
            stmt = stmt.where(AwardType.is_active.is_(True))
        return list(self.db.scalars(stmt))
