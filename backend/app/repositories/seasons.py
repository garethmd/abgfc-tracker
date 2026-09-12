from sqlalchemy import select, update

from app.models import Season
from app.repositories.base import BaseRepository


class SeasonRepository(BaseRepository[Season]):
    model = Season
    label = "Season"

    def list_all(self) -> list[Season]:
        return list(
            self.db.scalars(select(Season).order_by(Season.start_date.desc(), Season.id.desc()))
        )

    def get_current(self) -> Season | None:
        return self.db.scalar(select(Season).where(Season.is_current.is_(True)))

    def get_by_name(self, name: str) -> Season | None:
        return self.db.scalar(select(Season).where(Season.name == name))

    def set_current(self, season: Season) -> None:
        self.db.execute(update(Season).values(is_current=False))
        season.is_current = True
        self.db.flush()
