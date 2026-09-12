from sqlalchemy import select

from app.models import Team
from app.repositories.base import BaseRepository


class TeamRepository(BaseRepository[Team]):
    model = Team
    label = "Team"

    def list_all(self) -> list[Team]:
        return list(self.db.scalars(select(Team).order_by(Team.name)))

    def get_by_name(self, name: str) -> Team | None:
        return self.db.scalar(select(Team).where(Team.name == name))
