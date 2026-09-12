from sqlalchemy.orm import Session

from app.core.errors import AuthError, ValidationError
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories.users import UserRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    def authenticate(self, username: str, password: str) -> User:
        user = self.repo.get_by_username(username)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise AuthError("Incorrect username or password")
        return user

    def get_user(self, user_id: int) -> User | None:
        user = self.repo.get(user_id)
        return user if user and user.is_active else None

    def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(current, user.password_hash):
            raise ValidationError("Current password is incorrect")
        user.password_hash = hash_password(new)
        self.db.commit()
