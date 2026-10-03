from fastapi import APIRouter

from app.api.deps import DB, Access
from app.schemas.ground import GroundRead
from app.services.grounds import GroundService

router = APIRouter(prefix="/grounds", tags=["grounds"])


@router.get("/lookup", response_model=GroundRead)
def lookup_ground(q: str, db: DB, _: Access):
    """Where a ground is, for the little map on a fixture. `found` is false when nobody
    could place it - the page then just shows the name and a directions link."""
    ground = GroundService(db).lookup(q)
    if ground is None or ground.lat is None or ground.lon is None:
        return GroundRead(query=q, found=False)
    return GroundRead(
        query=q, found=True, display_name=ground.display_name, lat=ground.lat, lon=ground.lon
    )
