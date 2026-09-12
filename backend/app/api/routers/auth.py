from fastapi import APIRouter, Response

from app.api.deps import DB, Access, Config, CurrentUser
from app.core.security import SESSION_COOKIE, create_session_token
from app.models import UserRole
from app.repositories.club import ClubTeamRepository, CohortRepository, TeamSeasonRepository
from app.schemas.auth import ChangePasswordRequest, CohortAccess, LoginRequest, MeRead, TeamAccess
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=MeRead)
def login(data: LoginRequest, response: Response, db: DB, settings: Config):
    user = AuthService(db).authenticate(data.username, data.password)
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id, settings.secret_key),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
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
