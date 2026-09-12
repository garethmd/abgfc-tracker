from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
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
    _: CurrentUser,
    season_id: int | None = None,
    competition_id: int | None = None,
    status: FixtureStatus | None = None,
):
    return FixtureService(db).list_all(
        season_id=season_id, competition_id=competition_id, status=status
    )


@router.post("", response_model=FixtureDetail, status_code=201)
def create_fixture(data: FixtureCreate, db: DB, _: CurrentUser):
    svc = FixtureService(db)
    return svc.detail(svc.create(data).id)


@router.get("/{fixture_id}", response_model=FixtureDetail)
def get_fixture(fixture_id: int, db: DB, _: CurrentUser):
    return FixtureService(db).detail(fixture_id)


@router.patch("/{fixture_id}", response_model=FixtureDetail)
def update_fixture(fixture_id: int, data: FixtureUpdate, db: DB, _: CurrentUser):
    svc = FixtureService(db)
    svc.update(fixture_id, data)
    return svc.detail(fixture_id)


@router.delete("/{fixture_id}", status_code=204)
def delete_fixture(fixture_id: int, db: DB, _: CurrentUser):
    FixtureService(db).delete(fixture_id)


@router.put("/{fixture_id}/result", response_model=FixtureDetail)
def submit_result(fixture_id: int, data: ResultSubmit, db: DB, _: CurrentUser):
    """Post-match entry: appearances, goals/assists, awards and score in one write."""
    return FixtureService(db).submit_result(fixture_id, data)
