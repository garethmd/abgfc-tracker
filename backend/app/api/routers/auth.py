from fastapi import APIRouter, Response

from app.api.deps import DB, Config, CurrentUser
from app.core.security import SESSION_COOKIE, create_session_token
from app.schemas.auth import LoginRequest, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserRead)
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
    return user


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser):
    return user
