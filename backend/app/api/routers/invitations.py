"""Inviting parents, and seeing who can already get in.

Session-creating endpoints (accepting an invitation, signing in with a link) live in
the auth router with the rest of the cookie handling.
"""

from fastapi import APIRouter

from app.api.deps import DB, Access, Config
from app.schemas.invite import InviteCreate, InviteCreated, PlayerAccessRead
from app.services.invites import InviteService

router = APIRouter(tags=["invitations"])


@router.post("/invitations", response_model=InviteCreated, status_code=201)
def create_invitation(data: InviteCreate, db: DB, access: Access, settings: Config):
    """Invite a parent as the guardian of one child. Coach+ on that child's team.

    The response carries the link **once** so it can be sent by hand if email fails or
    the parent only uses WhatsApp; it is never returned again.
    """
    return InviteService(db, access, settings).create(data)


@router.get("/team-seasons/{team_season_id}/parents", response_model=list[PlayerAccessRead])
def team_parents(team_season_id: int, db: DB, access: Access, settings: Config):
    """Each child in the squad with the parents who can see the club, and any invitation
    still outstanding."""
    return InviteService(db, access, settings).list_for_team_season(team_season_id)


@router.delete("/invitations/{invite_id}", status_code=204)
def revoke_invitation(invite_id: int, db: DB, access: Access, settings: Config):
    InviteService(db, access, settings).revoke(invite_id)
