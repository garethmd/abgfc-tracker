from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.fixture import Fixture
    from app.models.player import SquadMember


class Season(TimestampMixin, Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    # Default match length; feeds time-on-pitch. FA U10 maximum is 50 minutes.
    match_minutes: Mapped[int] = mapped_column(Integer, default=50, server_default="50")
    # Exactly one season is current; enforced in the service layer, not the DB.
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    squad_members: Mapped[list["SquadMember"]] = relationship(back_populates="season")
    fixtures: Mapped[list["Fixture"]] = relationship(back_populates="season")
