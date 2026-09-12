from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.repositories.lookups import AwardTypeRepository, PositionRepository
from app.schemas.lookup import (
    AwardTypeRead,
    CompetitionCreate,
    CompetitionRead,
    CompetitionUpdate,
    PositionRead,
)
from app.schemas.team import TeamCreate, TeamRead, TeamUpdate
from app.services.lookups import CompetitionService, TeamService

router = APIRouter(tags=["lookups"])


@router.get("/positions", response_model=list[PositionRead])
def list_positions(db: DB, _: CurrentUser):
    return PositionRepository(db).list_all()


@router.get("/award-types", response_model=list[AwardTypeRead])
def list_award_types(db: DB, _: CurrentUser, active_only: bool = True):
    return AwardTypeRepository(db).list_all(active_only=active_only)


@router.get("/competitions", response_model=list[CompetitionRead])
def list_competitions(db: DB, _: CurrentUser):
    return CompetitionService(db).list_all()


@router.post("/competitions", response_model=CompetitionRead, status_code=201)
def create_competition(data: CompetitionCreate, db: DB, _: CurrentUser):
    return CompetitionService(db).create(data)


@router.patch("/competitions/{competition_id}", response_model=CompetitionRead)
def update_competition(competition_id: int, data: CompetitionUpdate, db: DB, _: CurrentUser):
    return CompetitionService(db).update(competition_id, data)


@router.delete("/competitions/{competition_id}", status_code=204)
def delete_competition(competition_id: int, db: DB, _: CurrentUser):
    CompetitionService(db).delete(competition_id)


@router.get("/teams", response_model=list[TeamRead])
def list_teams(db: DB, _: CurrentUser):
    return TeamService(db).list_all()


@router.post("/teams", response_model=TeamRead, status_code=201)
def create_team(data: TeamCreate, db: DB, _: CurrentUser):
    return TeamService(db).create(data)


@router.get("/teams/{team_id}", response_model=TeamRead)
def get_team(team_id: int, db: DB, _: CurrentUser):
    return TeamService(db).get(team_id)


@router.patch("/teams/{team_id}", response_model=TeamRead)
def update_team(team_id: int, data: TeamUpdate, db: DB, _: CurrentUser):
    return TeamService(db).update(team_id, data)


@router.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: int, db: DB, _: CurrentUser):
    TeamService(db).delete(team_id)
