from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import AuthError
from app.core.security import SESSION_COOKIE, read_session_token
from app.db.session import get_db
from app.models import User
from app.services.access import Access as AccessModel
from app.services.auth import AuthService

DB = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]


def get_current_user(
    db: DB,
    settings: Config,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    if not session:
        raise AuthError("Not signed in")
    user_id = read_session_token(session, settings.secret_key, settings.session_max_age_seconds)
    user = AuthService(db).get_user(user_id) if user_id else None
    if user is None:
        raise AuthError("Session expired - sign in again")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_access(db: DB, user: CurrentUser) -> AccessModel:
    return AccessModel.for_user(db, user)


Access = Annotated[AccessModel, Depends(get_access)]
