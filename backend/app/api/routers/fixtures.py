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
from app.schemas.note import MatchNoteCreate, MatchNoteRead, MatchNoteUpdate
from app.services.fixtures import FixtureService
from app.services.notes import MatchNoteService

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


# --- match notes (reports pasted from WhatsApp) -------------------------------------


@router.get("/{fixture_id}/notes", response_model=list[MatchNoteRead])
def list_notes(fixture_id: int, db: DB, access: Access):
    return MatchNoteService(db, access).list_for(fixture_id)


@router.post("/{fixture_id}/notes", response_model=MatchNoteRead, status_code=201)
def add_note(fixture_id: int, data: MatchNoteCreate, db: DB, access: Access):
    return MatchNoteService(db, access).add(fixture_id, data)


@router.patch("/{fixture_id}/notes/{note_id}", response_model=MatchNoteRead)
def update_note(fixture_id: int, note_id: int, data: MatchNoteUpdate, db: DB, access: Access):
    return MatchNoteService(db, access).update(fixture_id, note_id, data)


@router.delete("/{fixture_id}/notes/{note_id}", status_code=204)
def delete_note(fixture_id: int, note_id: int, db: DB, access: Access):
    MatchNoteService(db, access).delete(fixture_id, note_id)
