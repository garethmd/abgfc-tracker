from fastapi import APIRouter

from app.api.deps import DB, Access
from app.models import FixtureStatus
from app.schemas.fixture import (
    FixtureCreate,
    FixtureDetail,
    FixtureRead,
    FixtureUpdate,
    ResultSubmit,
)
from app.services.fixtures import FixtureService

router = APIRouter(prefix="/fixtures", tags=["fixtures"])


@router.get("", response_model=list[FixtureRead])
def list_fixtures(
    db: DB,
    access: Access,
    team_season_id: int | None = None,
    competition_id: int | None = None,
    status: FixtureStatus | None = None,
):
    return FixtureService(db, access).list_all(
        team_season_id=team_season_id, competition_id=competition_id, status=status
    )


@router.post("", response_model=FixtureDetail, status_code=201)
def create_fixture(data: FixtureCreate, db: DB, access: Access):
    svc = FixtureService(db, access)
    return svc.detail(svc.create(data).id)


@router.get("/{fixture_id}", response_model=FixtureDetail)
def get_fixture(fixture_id: int, db: DB, access: Access):
    return FixtureService(db, access).detail(fixture_id)


@router.patch("/{fixture_id}", response_model=FixtureDetail)
def update_fixture(fixture_id: int, data: FixtureUpdate, db: DB, access: Access):
    svc = FixtureService(db, access)
    svc.update(fixture_id, data)
    return svc.detail(fixture_id)


@router.delete("/{fixture_id}", status_code=204)
def delete_fixture(fixture_id: int, db: DB, access: Access):
    FixtureService(db, access).delete(fixture_id)


@router.put("/{fixture_id}/result", response_model=FixtureDetail)
def submit_result(fixture_id: int, data: ResultSubmit, db: DB, access: Access):
    """Post-match entry: appearances, goals/assists, awards and score in one write."""
    return FixtureService(db, access).submit_result(fixture_id, data)
