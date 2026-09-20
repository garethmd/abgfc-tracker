from fastapi import APIRouter

from app.api.deps import DB, Access
from app.repositories.lookups import PositionRepository
from app.schemas.lookup import (
    AwardTypeCreate,
    AwardTypeRead,
    AwardTypeUpdate,
    CompetitionCreate,
    CompetitionRead,
    CompetitionUpdate,
    PositionRead,
)
from app.schemas.team import HeadToHead, TeamCreate, TeamRead, TeamUpdate
from app.services.lookups import AwardTypeService, CompetitionService, TeamService

router = APIRouter(tags=["lookups"])


@router.get("/positions", response_model=list[PositionRead])
def list_positions(db: DB, _: Access):
    return PositionRepository(db).list_all()


@router.get("/award-types", response_model=list[AwardTypeRead])
def list_award_types(
    db: DB, access: Access, club_team_id: int | None = None, active_only: bool = True
):
    """Club-wide award types, plus the given team's own."""
    return AwardTypeService(db, access).list_for_team(club_team_id, active_only=active_only)


@router.post("/award-types", response_model=AwardTypeRead, status_code=201)
def create_award_type(data: AwardTypeCreate, db: DB, access: Access):
    return AwardTypeService(db, access).create(data)


@router.patch("/award-types/{award_type_id}", response_model=AwardTypeRead)
def update_award_type(award_type_id: int, data: AwardTypeUpdate, db: DB, access: Access):
    return AwardTypeService(db, access).update(award_type_id, data)


@router.get("/competitions", response_model=list[CompetitionRead])
def list_competitions(db: DB, _: Access):
    return CompetitionService(db).list_all()


@router.post("/competitions", response_model=CompetitionRead, status_code=201)
def create_competition(data: CompetitionCreate, db: DB, _: Access):
    return CompetitionService(db).create(data)


@router.patch("/competitions/{competition_id}", response_model=CompetitionRead)
def update_competition(competition_id: int, data: CompetitionUpdate, db: DB, _: Access):
    return CompetitionService(db).update(competition_id, data)


@router.delete("/competitions/{competition_id}", status_code=204)
def delete_competition(competition_id: int, db: DB, _: Access):
    CompetitionService(db).delete(competition_id)


@router.get("/teams", response_model=list[TeamRead])
def list_teams(db: DB, _: Access):
    return TeamService(db).list_all()


@router.post("/teams", response_model=TeamRead, status_code=201)
def create_team(data: TeamCreate, db: DB, _: Access):
    return TeamService(db).create(data)


@router.get("/teams/{team_id}", response_model=TeamRead)
def get_team(team_id: int, db: DB, _: Access):
    return TeamService(db).get(team_id)


@router.get("/teams/{team_id}/head-to-head", response_model=HeadToHead)
def head_to_head(team_id: int, db: DB, access: Access, club_team_id: int | None = None):
    """Our record and every fixture against this opposition (scoped to teams you can see;
    pass club_team_id to restrict to one of our teams)."""
    return TeamService(db).head_to_head(team_id, access, club_team_id)


@router.patch("/teams/{team_id}", response_model=TeamRead)
def update_team(team_id: int, data: TeamUpdate, db: DB, _: Access):
    return TeamService(db).update(team_id, data)


@router.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: int, db: DB, _: Access):
    TeamService(db).delete(team_id)
