from pydantic import Field

from app.models.enums import RoleScope, UserRole
from app.schemas.club import ClubTeamRead, CohortRead
from app.schemas.common import InputModel, ORMModel


class LoginRequest(InputModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)


class ChangePasswordRequest(InputModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class RoleRead(ORMModel):
    role: UserRole
    scope_type: RoleScope
    scope_id: int | None


class TeamAccess(ORMModel):
    """One team the signed-in user can see, with what they may do there."""

    team: ClubTeamRead
    role: UserRole
    current_team_season_id: int | None


class CohortAccess(ORMModel):
    cohort: CohortRead
    role: UserRole


class MeRead(ORMModel):
    id: int
    username: str
    display_name: str | None
    roles: list[RoleRead]
    club_role: UserRole | None
    cohorts: list[CohortAccess]
    teams: list[TeamAccess]


# --- admin -----------------------------------------------------------------


class RoleAssignment(InputModel):
    role: UserRole
    scope_type: RoleScope
    scope_id: int | None = None


class UserCreate(InputModel):
    username: str = Field(min_length=2, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    display_name: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    roles: list[RoleAssignment] = []


class UserUpdate(InputModel):
    display_name: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class SetPasswordRequest(InputModel):
    new_password: str = Field(min_length=8, max_length=200)


class UserAdminRead(ORMModel):
    id: int
    username: str
    display_name: str | None
    is_active: bool
    roles: list[RoleRead]
