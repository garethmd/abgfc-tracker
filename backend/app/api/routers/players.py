from fastapi import APIRouter

from app.api.deps import DB, Access
from app.core.errors import NotFoundError
from app.schemas.player import (
    PlayerCreate,
    PlayerMove,
    PlayerRead,
    PlayerUpdate,
    SquadMemberRead,
)
from app.schemas.stats import PlayerStatsRow
from app.services.players import PlayerService
from app.services.stats import StatsService

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerRead])
def list_players(db: DB, access: Access, cohort_id: int | None = None, include_left: bool = True):
    return PlayerService(db, access).list_visible(cohort_id=cohort_id, include_left=include_left)


@router.post("", response_model=PlayerRead, status_code=201)
def create_player(data: PlayerCreate, db: DB, access: Access):
    return PlayerService(db, access).create(data)


@router.get("/{player_id}", response_model=PlayerRead)
def get_player(player_id: int, db: DB, access: Access):
    return PlayerService(db, access).get(player_id)


@router.patch("/{player_id}", response_model=PlayerRead)
def update_player(player_id: int, data: PlayerUpdate, db: DB, access: Access):
    return PlayerService(db, access).update(player_id, data)


@router.get("/{player_id}/memberships", response_model=list[SquadMemberRead])
def player_memberships(player_id: int, db: DB, access: Access):
    """Every team-season the player has been in (that the caller can see)."""
    return PlayerService(db, access).memberships(player_id)


@router.get("/{player_id}/stats", response_model=PlayerStatsRow)
def player_stats(player_id: int, team_season_id: int, db: DB, access: Access):
    PlayerService(db, access).get(player_id)
    row = StatsService(db, access).player_season(player_id, team_season_id)
    if row is None:
        raise NotFoundError("Player has no record in this team season")
    return row


@router.post("/{player_id}/move", response_model=SquadMemberRead)
def move_player(player_id: int, data: PlayerMove, db: DB, access: Access):
    return PlayerService(db, access).move(player_id, data)
