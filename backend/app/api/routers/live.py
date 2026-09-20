from fastapi import APIRouter

from app.api.deps import DB, Access
from app.schemas.fixture import FixtureDetail, LiveGoal, LiveSquad
from app.services.live import LiveMatchService

router = APIRouter(prefix="/fixtures/{fixture_id}/live", tags=["live"])


@router.post("/start", response_model=FixtureDetail)
def start_live(fixture_id: int, data: LiveSquad, db: DB, access: Access):
    """Kick off: the fixture goes live with today's squad and a 0-0 score."""
    return LiveMatchService(db, access).start(fixture_id, data)


@router.put("/squad", response_model=FixtureDetail)
def set_live_squad(fixture_id: int, data: LiveSquad, db: DB, access: Access):
    return LiveMatchService(db, access).set_squad(fixture_id, data)


@router.post("/goals", response_model=FixtureDetail)
def add_live_goal(fixture_id: int, data: LiveGoal, db: DB, access: Access):
    return LiveMatchService(db, access).add_goal(fixture_id, data)


@router.delete("/goals/{event_id}", response_model=FixtureDetail)
def remove_live_goal(fixture_id: int, event_id: int, db: DB, access: Access):
    return LiveMatchService(db, access).remove_goal(fixture_id, event_id)


@router.post("/against", response_model=FixtureDetail)
def live_goal_against(fixture_id: int, db: DB, access: Access):
    return LiveMatchService(db, access).goal_against(fixture_id)


@router.delete("/against", response_model=FixtureDetail)
def remove_live_goal_against(fixture_id: int, db: DB, access: Access):
    return LiveMatchService(db, access).remove_goal_against(fixture_id)


@router.post("/finish", response_model=FixtureDetail)
def finish_live(fixture_id: int, db: DB, access: Access):
    """Full time: the fixture becomes 'played', exactly as PUT /result would leave it."""
    return LiveMatchService(db, access).finish(fixture_id)


@router.delete("", status_code=204)
def abandon_live(fixture_id: int, db: DB, access: Access):
    """Started by mistake: clears everything and returns the fixture to scheduled."""
    LiveMatchService(db, access).abandon(fixture_id)
