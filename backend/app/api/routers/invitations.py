"""Inviting parents, and seeing who can already get in.

Session-creating endpoints (accepting an invitation, signing in with a link) live in
the auth router with the rest of the cookie handling.
"""

from fastapi import APIRouter

from app.api.deps import DB, Access, Config
from app.schemas.invite import InviteCreate, InviteCreated, TeamParentsRead
from app.services.invites import InviteService

router = APIRouter(tags=["invitations"])


@router.post("/invitations", response_model=InviteCreated, status_code=201)
def create_invitation(data: InviteCreate, db: DB, access: Access, settings: Config):
    """Invite a parent as the guardian of one child. Coach+ on that child's team.

    The response carries the link **once** so it can be sent by hand if email fails or
    the parent only uses WhatsApp; it is never returned again.
    """
    return InviteService(db, access, settings).create(data)


@router.get("/team-seasons/{team_season_id}/parents", response_model=TeamParentsRead)
def team_parents(team_season_id: int, db: DB, access: Access, settings: Config):
    """Each child in the squad with the parents who can see the club and any invitation
    still outstanding, plus parents whose children have all left - the accounts to remove."""
    return InviteService(db, access, settings).list_for_team_season(team_season_id)


@router.delete("/parents/{user_id}", status_code=204)
def delete_parent(user_id: int, db: DB, access: Access, settings: Config):
    """Erase a parent's account - the shortcut for removing every child at once. Frees
    the address to be invited again."""
    InviteService(db, access, settings).delete_parent(user_id)


@router.delete("/parents/{user_id}/children/{player_id}", status_code=204)
def unlink_parent(user_id: int, player_id: int, db: DB, access: Access, settings: Config):
    """Remove this parent's access to this child. If it was their last child anywhere,
    the account goes with it - an account is exactly its links."""
    InviteService(db, access, settings).unlink(user_id, player_id)


@router.post("/parents/{user_id}/sign-out", status_code=204)
def sign_parent_out(user_id: int, db: DB, access: Access, settings: Config):
    """Sign every device out but keep the account - a phone left on a bus."""
    InviteService(db, access, settings).sign_out_everywhere(user_id)


@router.delete("/invitations/{invite_id}", status_code=204)
def revoke_invitation(invite_id: int, db: DB, access: Access, settings: Config):
    InviteService(db, access, settings).revoke(invite_id)
