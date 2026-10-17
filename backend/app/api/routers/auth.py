from fastapi import APIRouter, Request, Response

from app.api.deps import DB, Access, Config, CurrentUser
from app.core.ratelimit import signin_links, token_attempts
from app.core.security import SESSION_COOKIE, create_session_token
from app.models import User, UserRole
from app.repositories.club import ClubTeamRepository, CohortRepository, TeamSeasonRepository
from app.schemas.auth import ChangePasswordRequest, CohortAccess, LoginRequest, MeRead, TeamAccess
from app.schemas.invite import (
    ForgotPasswordRequest,
    InviteAccept,
    InvitePreview,
    PasswordReset,
)
from app.schemas.passkey import (
    PasskeyAuthenticate,
    PasskeyRead,
    PasskeyRegister,
)
from app.services.auth import AuthService
from app.services.invites import InviteService
from app.services.passkeys import PasskeyService, passkey_label

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=MeRead)
def login(data: LoginRequest, response: Response, db: DB, settings: Config):
    """Username and password - coaches and admins. Unchanged, and a parent account can
    never come through here: it has no password hash to match."""
    user = AuthService(db).authenticate(data.username, data.password)
    return _sign_in(response, user, db, settings)


# --- parents: no password, just a link ---------------------------------------------


@router.post("/forgot-password", status_code=204)
def forgot_password(data: ForgotPasswordRequest, request: Request, db: DB, settings: Config):
    """Email a way back in: a reset link, or - for a parent from before passwords - the
    sign-in link they have always used. Always 204, whether or not that address has an
    account; an unauthenticated caller doesn't get to find out which are registered."""
    signin_links.check(f"email:{data.email}")
    signin_links.check(f"ip:{_client(request)}")
    InviteService(db, None, settings).forgot_password(data.email)


@router.post("/reset-password/{token}", response_model=MeRead)
def reset_password(
    token: str,
    data: PasswordReset,
    request: Request,
    response: Response,
    db: DB,
    settings: Config,
):
    """Spend the reset link, set the new password and sign in. Other sessions end."""
    token_attempts.check(f"ip:{_client(request)}")
    user = InviteService(db, None, settings).reset_password(token, data.new_password)
    return _sign_in(response, user, db, settings)


@router.post("/set-password", status_code=204)
def set_first_password(data: PasswordReset, db: DB, settings: Config, user: CurrentUser):
    """A parent who joined before passwords, choosing one. Being signed in is the proof;
    there is no current password to give."""
    InviteService(db, None, settings).set_first_password(user, data.new_password)


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


# --- passkeys ----------------------------------------------------------------------


@router.post("/passkeys/options")
def passkey_registration_options(db: DB, settings: Config, user: CurrentUser):
    """Start registering a passkey. Only ever for an account already signed in - that
    is what binds the new credential to the right person."""
    return PasskeyService(db, settings).registration_options(user)


@router.post("/passkeys", response_model=PasskeyRead, status_code=201)
def register_passkey(data: PasskeyRegister, db: DB, settings: Config, user: CurrentUser):
    p = PasskeyService(db, settings).register(user, data.credential, data.label)
    return PasskeyRead(
        id=p.id, label=passkey_label(p), created_at=p.created_at, last_used_at=p.last_used_at
    )


@router.get("/passkeys", response_model=list[PasskeyRead])
def my_passkeys(user: CurrentUser):
    return [
        PasskeyRead(
            id=p.id, label=passkey_label(p), created_at=p.created_at, last_used_at=p.last_used_at
        )
        for p in user.passkeys
    ]


@router.delete("/passkeys/{passkey_id}", status_code=204)
def remove_passkey(passkey_id: int, db: DB, settings: Config, user: CurrentUser):
    PasskeyService(db, settings).remove(user, passkey_id)


@router.post("/passkeys/signin/options")
def passkey_signin_options(request: Request, db: DB, settings: Config):
    """No account is named and nothing here says whether one exists: the credential is
    discoverable, so the phone decides which account it holds."""
    token_attempts.check(f"ip:{_client(request)}")
    return PasskeyService(db, settings).authentication_options()


@router.post("/passkeys/signin", response_model=MeRead)
def passkey_signin(
    data: PasskeyAuthenticate, request: Request, response: Response, db: DB, settings: Config
):
    token_attempts.check(f"ip:{_client(request)}")
    user = PasskeyService(db, settings).authenticate(data.credential)
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
        passkey_count=len(access.user.passkeys),
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
