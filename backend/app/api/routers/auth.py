from fastapi import APIRouter, Request, Response

from app.api.deps import DB, Access, Config, CurrentUser
from app.core.ratelimit import signin_links, token_attempts
from app.core.security import SESSION_COOKIE, create_session_token
from app.models import User, UserRole
from app.repositories.club import ClubTeamRepository, CohortRepository, TeamSeasonRepository
from app.schemas.auth import ChangePasswordRequest, CohortAccess, LoginRequest, MeRead, TeamAccess
from app.schemas.invite import InviteAccept, InvitePreview, SigninLinkRequest
from app.services.auth import AuthService
from app.services.invites import InviteService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=MeRead)
def login(data: LoginRequest, response: Response, db: DB, settings: Config):
    """Username and password - coaches and admins. Unchanged, and a parent account can
    never come through here: it has no password hash to match."""
    user = AuthService(db).authenticate(data.username, data.password)
    return _sign_in(response, user, db, settings)


# --- parents: no password, just a link ---------------------------------------------


@router.post("/signin-link", status_code=204)
def request_signin_link(data: SigninLinkRequest, request: Request, db: DB, settings: Config):
    """Email a sign-in link. Always 204, whether or not that address has an account -
    an unauthenticated caller doesn't get to find out which addresses are registered."""
    signin_links.check(f"email:{data.email}")
    signin_links.check(f"ip:{_client(request)}")
    InviteService(db, None, settings).request_signin_link(data.email)


@router.post("/signin-link/{token}", response_model=MeRead)
def use_signin_link(token: str, request: Request, response: Response, db: DB, settings: Config):
    token_attempts.check(f"ip:{_client(request)}")
    user = InviteService(db, None, settings).consume_signin(token)
    return _sign_in(response, user, db, settings)


@router.get("/invitations/{token}", response_model=InvitePreview)
def preview_invitation(token: str, request: Request, db: DB, settings: Config):
    """What the invitation is for. Reading does not spend the token - mail scanners
    follow links, and spending it here would break the invitation before the parent
    ever saw it."""
    token_attempts.check(f"ip:{_client(request)}")
    return InviteService(db, None, settings).preview(token)


@router.post("/invitations/{token}/accept", response_model=MeRead)
def accept_invitation(
    token: str,
    data: InviteAccept,
    request: Request,
    response: Response,
    db: DB,
    settings: Config,
):
    """Create the parent's account and sign them in. This is where the token is spent."""
    token_attempts.check(f"ip:{_client(request)}")
    user = InviteService(db, None, settings).accept(token, data)
    return _sign_in(response, user, db, settings)


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _sign_in(response: Response, user: User, db: DB, settings: Config) -> MeRead:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id, settings.secret_key, user.session_version),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )
    from app.services.access import Access as AccessModel

    return _me(db, AccessModel.for_user(db, user))


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeRead)
def me(db: DB, access: Access):
    return _me(db, access)


@router.post("/change-password", status_code=204)
def change_password(data: ChangePasswordRequest, db: DB, user: CurrentUser):
    AuthService(db).change_password(user, data.current_password, data.new_password)


def _me(db, access) -> MeRead:
    """The signed-in user plus everything they can reach - drives routing on the client."""
    teams = ClubTeamRepository(db).list_all(ids=access.visible_team_ids())
    team_seasons = TeamSeasonRepository(db)
    cohorts = CohortRepository(db).list_all(ids=access.visible_cohort_ids())
    return MeRead(
        id=access.user.id,
        username=access.user.username,
        email=access.user.email,
        has_password=access.user.password_hash is not None,
        display_name=access.user.display_name,
        roles=list(access.user.roles),
        club_role=access.club_role,
        cohorts=[
            CohortAccess(cohort=c, role=access.role_for_cohort(c.id) or UserRole.VIEWER)
            for c in cohorts
        ],
        teams=[
            TeamAccess(
                team=t,
                role=access.role_for_team(t.id, t.cohort_id) or UserRole.VIEWER,
                current_team_season_id=(
                    (team_seasons.get_current(t.id) or _latest(team_seasons, t.id)).id
                    if team_seasons.list_for_team(t.id)
                    else None
                ),
            )
            for t in teams
            if t.is_active
        ],
    )


def _latest(repo: TeamSeasonRepository, team_id: int):
    return repo.list_for_team(team_id)[0]
