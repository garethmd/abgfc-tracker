from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ground(Base):
    """A ground we have looked up on OpenStreetMap, cached by the text we searched for.

    Grounds are free text on fixtures and teams, so the cache is keyed by the normalised
    query rather than by any team: a one-off venue maps as readily as a league ground, and
    the same place typed on twenty fixtures is looked up once. A miss is cached too (lat
    and lon stay NULL) so a name nobody can find isn't retried on every page view.
    """

    __tablename__ = "grounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(String(200), unique=True)  # normalised search text
    display_name: Mapped[str | None] = mapped_column(String(300))  # what OSM calls it
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    looked_up_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
