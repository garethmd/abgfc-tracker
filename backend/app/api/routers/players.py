from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile

from app.api.deps import DB, Access
from app.core.errors import NotFoundError
from app.schemas.player import (
    MembershipRead,
    PlayerCreate,
    PlayerMove,
    PlayerRead,
    PlayerUpdate,
    SquadMemberRead,
)
from app.schemas.stats import PlayerStatsRow
from app.services.media import PlayerPhotoService
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


@router.get("/{player_id}/memberships", response_model=list[MembershipRead])
def player_memberships(player_id: int, db: DB, access: Access):
    """Every team-season the player has been in (that the caller can see)."""
    return [
        MembershipRead(
            id=m.id,
            team_season_id=m.team_season_id,
            team_id=m.team_season.club_team_id,
            team_name=m.team_season.club_team.name,
            team_slug=m.team_season.club_team.slug,
            season_name=m.team_season.season.name,
            age_group=m.team_season.age_group,
            squad_number=m.squad_number,
            joined_at=m.joined_at,
            left_at=m.left_at,
        )
        for m in PlayerService(db, access).memberships(player_id)
    ]


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


# --- profile photo ---------------------------------------------------------------


@router.put("/{player_id}/photo", response_model=PlayerRead)
async def set_photo(player_id: int, db: DB, access: Access, file: Annotated[UploadFile, File()]):
    """Upload (or replace) the profile photo. Re-encoded server-side: metadata stripped,
    resized, stored on the private media volume. Coaches only."""
    data = await file.read()
    PlayerPhotoService(db, access).set_photo(player_id, data, file.filename)
    return PlayerService(db, access).get(player_id)


@router.get(
    "/{player_id}/photo",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}, "description": "The photo"}},
)
def get_photo(player_id: int, db: DB, access: Access, size: str = "full"):
    """The player's photo (`size=thumb` for a 256px square). Access-checked like the player;
    cacheable per user because the URL carries the media id."""
    data, key = PlayerPhotoService(db, access).get_photo(player_id, size)
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=86400", "ETag": f'"{key}-{size}"'},
    )


@router.delete("/{player_id}/photo", status_code=204)
def delete_photo(player_id: int, db: DB, access: Access):
    PlayerPhotoService(db, access).remove_photo(player_id)
