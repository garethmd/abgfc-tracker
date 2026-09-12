from fastapi import APIRouter

from app.api.deps import DB, Access
from app.schemas.auth import (
    RoleAssignment,
    SetPasswordRequest,
    UserAdminRead,
    UserCreate,
    UserUpdate,
)
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserAdminRead])
def list_users(db: DB, access: Access):
    """Users within the caller's admin scope."""
    return UserService(db, access).list_managed()


@router.post("", response_model=UserAdminRead, status_code=201)
def create_user(data: UserCreate, db: DB, access: Access):
    return UserService(db, access).create(data)


@router.get("/{user_id}", response_model=UserAdminRead)
def get_user(user_id: int, db: DB, access: Access):
    return UserService(db, access).get(user_id)


@router.patch("/{user_id}", response_model=UserAdminRead)
def update_user(user_id: int, data: UserUpdate, db: DB, access: Access):
    return UserService(db, access).update(user_id, data)


@router.put("/{user_id}/roles", response_model=UserAdminRead)
def set_roles(user_id: int, roles: list[RoleAssignment], db: DB, access: Access):
    return UserService(db, access).set_roles(user_id, roles)


@router.post("/{user_id}/password", status_code=204)
def set_password(user_id: int, data: SetPasswordRequest, db: DB, access: Access):
    """Admin reset - the "forgot password" path."""
    UserService(db, access).set_password(user_id, data.new_password)
