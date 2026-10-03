from app.schemas.common import ORMModel


class GroundRead(ORMModel):
    """A ground placed on the map, or not placeable."""

    query: str
    found: bool
    display_name: str | None = None
    lat: float | None = None
    lon: float | None = None
