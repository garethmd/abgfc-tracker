from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.schemas.player import SquadMemberRead, SquadMemberUpsert
from app.schemas.season import SeasonCreate, SeasonRead, SeasonUpdate
from app.schemas.stats import Leaderboard, SeasonSummary
from app.services.players import PlayerService
from app.services.seasons import SeasonService
from app.services.stats import StatsService

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("", response_model=list[SeasonRead])
def list_seasons(db: DB, _: CurrentUser):
    return SeasonService(db).list_all()


@router.post("", response_model=SeasonRead, status_code=201)
def create_season(data: SeasonCreate, db: DB, _: CurrentUser):
    return SeasonService(db).create(data)


@router.get("/current", response_model=SeasonRead)
def current_season(db: DB, _: CurrentUser):
    return SeasonService(db).current()


@router.get("/{season_id}", response_model=SeasonRead)
def get_season(season_id: int, db: DB, _: CurrentUser):
    return SeasonService(db).get(season_id)


@router.patch("/{season_id}", response_model=SeasonRead)
def update_season(season_id: int, data: SeasonUpdate, db: DB, _: CurrentUser):
    return SeasonService(db).update(season_id, data)


@router.post("/{season_id}/make-current", response_model=SeasonRead)
def make_current(season_id: int, db: DB, _: CurrentUser):
    return SeasonService(db).make_current(season_id)


@router.delete("/{season_id}", status_code=204)
def delete_season(season_id: int, db: DB, _: CurrentUser):
    SeasonService(db).delete(season_id)


# --- squad ---------------------------------------------------------------------


@router.get("/{season_id}/squad", response_model=list[SquadMemberRead])
def list_squad(season_id: int, db: DB, _: CurrentUser):
    return PlayerService(db).squad_for(season_id)


@router.put("/{season_id}/squad/{player_id}", response_model=SquadMemberRead)
def upsert_squad_member(
    season_id: int, player_id: int, data: SquadMemberUpsert, db: DB, _: CurrentUser
):
    return PlayerService(db).upsert_member(season_id, player_id, data)


@router.delete("/{season_id}/squad/{player_id}", status_code=204)
def remove_squad_member(season_id: int, player_id: int, db: DB, _: CurrentUser):
    PlayerService(db).remove_member(season_id, player_id)


# --- stats ---------------------------------------------------------------------


@router.get("/{season_id}/stats/summary", response_model=SeasonSummary)
def season_summary(season_id: int, db: DB, _: CurrentUser):
    return StatsService(db).season_summary(season_id)


@router.get("/{season_id}/stats/leaderboard", response_model=Leaderboard)
def season_leaderboard(season_id: int, db: DB, _: CurrentUser, competition_type: str | None = None):
    return StatsService(db).leaderboard(season_id, competition_type)
