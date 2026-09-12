from fastapi import APIRouter

from app.api.deps import DB, Access
from app.schemas.season import SeasonCreate, SeasonRead, SeasonUpdate
from app.services.seasons import SeasonService

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("", response_model=list[SeasonRead])
def list_seasons(db: DB, access: Access):
    return SeasonService(db, access).list_all()


@router.post("", response_model=SeasonRead, status_code=201)
def create_season(data: SeasonCreate, db: DB, access: Access):
    return SeasonService(db, access).create(data)


@router.get("/{season_id}", response_model=SeasonRead)
def get_season(season_id: int, db: DB, access: Access):
    return SeasonService(db, access).get(season_id)


@router.patch("/{season_id}", response_model=SeasonRead)
def update_season(season_id: int, data: SeasonUpdate, db: DB, access: Access):
    return SeasonService(db, access).update(season_id, data)


@router.delete("/{season_id}", status_code=204)
def delete_season(season_id: int, db: DB, access: Access):
    SeasonService(db, access).delete(season_id)
