from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AuthError
from app.core.security import verify_password
from app.models import User


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate(self, username: str, password: str) -> User:
        user = self.db.scalar(select(User).where(User.username == username))
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthError("Incorrect username or password")
        return user

    def get_user(self, user_id: int) -> User | None:
        user = self.db.get(User, user_id)
        return user if user and user.is_active else None
