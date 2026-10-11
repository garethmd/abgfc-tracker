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
    still outstanding, plus parents whose children have all left - the accounts to close."""
    return InviteService(db, access, settings).list_for_team_season(team_season_id)


@router.post("/parents/{user_id}/close", status_code=204)
def close_parent(user_id: int, db: DB, access: Access, settings: Config):
    """Stop this parent getting in - a child who has left, or a lost phone. Immediate."""
    InviteService(db, access, settings).close(user_id)


@router.post("/parents/{user_id}/reopen", status_code=204)
def reopen_parent(user_id: int, db: DB, access: Access, settings: Config):
    InviteService(db, access, settings).reopen(user_id)


@router.delete("/parents/{user_id}/children/{player_id}", status_code=204)
def unlink_parent(user_id: int, player_id: int, db: DB, access: Access, settings: Config):
    """Remove this parent's access to this child. Their account survives if they have
    another child here; otherwise they lose the age group with it."""
    InviteService(db, access, settings).unlink(user_id, player_id)


@router.post("/parents/{user_id}/email-signin", status_code=204)
def set_parent_email_signin(user_id: int, allowed: bool, db: DB, access: Access, settings: Config):
    """Let this parent keep using emailed links even though they have a passkey - for a
    phone that can't hold one. Never automatic."""
    InviteService(db, access, settings).set_email_signin(user_id, allowed)


@router.post("/parents/{user_id}/sign-out", status_code=204)
def sign_parent_out(user_id: int, db: DB, access: Access, settings: Config):
    """Sign every device out but keep the account - a phone left on a bus."""
    InviteService(db, access, settings).sign_out_everywhere(user_id)


@router.delete("/invitations/{invite_id}", status_code=204)
def revoke_invitation(invite_id: int, db: DB, access: Access, settings: Config):
    InviteService(db, access, settings).revoke(invite_id)
