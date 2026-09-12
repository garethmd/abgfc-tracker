from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User
    label = "User"

    def get(self, id: int) -> User | None:
        return self.db.scalar(select(User).where(User.id == id).options(selectinload(User.roles)))

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(
            select(User).where(User.username == username).options(selectinload(User.roles))
        )

    def list_all(self) -> list[User]:
        return list(
            self.db.scalars(select(User).options(selectinload(User.roles)).order_by(User.username))
        )
