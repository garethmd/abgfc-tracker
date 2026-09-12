from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.base import Base


class BaseRepository[ModelT: Base]:
    model: type[ModelT]
    label: str = "Record"

    def __init__(self, db: Session):
        self.db = db

    def get(self, id: int) -> ModelT | None:
        return self.db.get(self.model, id)

    def get_or_404(self, id: int) -> ModelT:
        obj = self.get(id)
        if obj is None:
            raise NotFoundError(f"{self.label} {id} not found")
        return obj

    def list_all(self) -> list[ModelT]:
        return list(self.db.scalars(select(self.model).order_by(self.model.id)))

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()
