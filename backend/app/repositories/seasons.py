from sqlalchemy import select

from app.models import Season
from app.repositories.base import BaseRepository


class SeasonRepository(BaseRepository[Season]):
    model = Season
    label = "Season"

    def list_all(self) -> list[Season]:
        return list(
            self.db.scalars(select(Season).order_by(Season.start_date.desc(), Season.id.desc()))
        )

    def get_by_name(self, name: str) -> Season | None:
        return self.db.scalar(select(Season).where(Season.name == name))
