from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core.errors import NotFoundError
from app.schemas.player import PlayerCreate, PlayerRead, PlayerUpdate
from app.schemas.stats import PlayerStatsRow
from app.services.players import PlayerService
from app.services.seasons import SeasonService
from app.services.stats import StatsService

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerRead])
def list_players(db: DB, _: CurrentUser, include_left: bool = True):
    return PlayerService(db).list_all(include_left=include_left)


@router.post("", response_model=PlayerRead, status_code=201)
def create_player(data: PlayerCreate, db: DB, _: CurrentUser):
    return PlayerService(db).create(data)


@router.get("/{player_id}", response_model=PlayerRead)
def get_player(player_id: int, db: DB, _: CurrentUser):
    return PlayerService(db).get(player_id)


@router.patch("/{player_id}", response_model=PlayerRead)
def update_player(player_id: int, data: PlayerUpdate, db: DB, _: CurrentUser):
    return PlayerService(db).update(player_id, data)


@router.get("/{player_id}/stats", response_model=PlayerStatsRow)
def player_stats(player_id: int, db: DB, _: CurrentUser, season_id: int | None = None):
    PlayerService(db).get(player_id)
    sid = season_id if season_id is not None else SeasonService(db).current().id
    row = StatsService(db).player_season(player_id, sid)
    if row is None:
        raise NotFoundError("Player has no record in this season")
    return row
