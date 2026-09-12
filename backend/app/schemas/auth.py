from pydantic import Field

from app.models.enums import UserRole
from app.schemas.common import InputModel, ORMModel


class LoginRequest(InputModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)


class UserRead(ORMModel):
    id: int
    username: str
    role: UserRole
