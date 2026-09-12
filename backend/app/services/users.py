"""Coach accounts. An admin can manage users within their own scope: a club admin
anyone, a cohort admin the coaches of their age group's teams, a team admin their team."""

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, ValidationError
from app.core.security import hash_password
from app.models import RoleScope, User, UserRole
from app.models import UserRoleAssignment as RoleRow
from app.repositories.club import ClubTeamRepository, CohortRepository
from app.repositories.users import UserRepository
from app.schemas.auth import RoleAssignment, UserCreate, UserUpdate
from app.services.access import Access


class UserService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.repo = UserRepository(db)

    def _can_grant(self, r: RoleAssignment) -> bool:
        """You can grant a role only within a scope where you are an admin."""
        if r.scope_type == RoleScope.CLUB:
            return self.access.is_club_admin
        if r.scope_type == RoleScope.COHORT:
            return (self.access.role_for_cohort(r.scope_id) or UserRole.VIEWER) == UserRole.ADMIN
        team = ClubTeamRepository(self.db).get(r.scope_id)
        return (
            team is not None
            and self.access.role_for_team(team.id, team.cohort_id) == UserRole.ADMIN
        )

    def _manages(self, user: User) -> bool:
        """Every role the user holds is within a scope this caller administers."""
        if not user.roles:
            return self.access.is_club_admin or bool(
                self.access.cohort_roles or self.access.team_roles
            )
        return all(
            self._can_grant(
                RoleAssignment(role=r.role, scope_type=r.scope_type, scope_id=r.scope_id)
            )
            for r in user.roles
        )

    def _require_admin_somewhere(self) -> None:
        if not (
            self.access.is_club_admin
            or UserRole.ADMIN in self.access.cohort_roles.values()
            or UserRole.ADMIN in self.access.team_roles.values()
        ):
            raise ForbiddenError("Admin access required")

    def list_managed(self) -> list[User]:
        self._require_admin_somewhere()
        return [u for u in self.repo.list_all() if self._manages(u)]

    def get(self, id: int) -> User:
        self._require_admin_somewhere()
        user = self.repo.get_or_404(id)
        if not self._manages(user):
            raise ForbiddenError("That user is outside your scope")
        return user

    def create(self, data: UserCreate) -> User:
        self._require_admin_somewhere()
        if not data.roles:
            raise ValidationError("Give the user at least one role")
        for r in data.roles:
            self._validate(r)
        if self.repo.get_by_username(data.username):
            raise ConflictError(f"Username '{data.username}' is taken")
        user = User(
            username=data.username,
            display_name=data.display_name,
            password_hash=hash_password(data.password),
        )
        user.roles = [
            RoleRow(role=r.role, scope_type=r.scope_type, scope_id=r.scope_id) for r in data.roles
        ]
        self.repo.add(user)
        self.db.commit()
        return self.repo.get(user.id)

    def update(self, id: int, data: UserUpdate) -> User:
        user = self.get(id)
        if user.id == self.access.user.id and data.is_active is False:
            raise ValidationError("You can't deactivate yourself")
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(user, k, v)
        self.db.commit()
        return user

    def set_roles(self, id: int, roles: list[RoleAssignment]) -> User:
        user = self.get(id)
        if not roles:
            raise ValidationError("A user needs at least one role")
        for r in roles:
            self._validate(r)
        if user.id == self.access.user.id and self.access.is_club_admin:
            if not any(r.scope_type == RoleScope.CLUB and r.role == UserRole.ADMIN for r in roles):
                raise ValidationError("You can't remove your own club admin role")
        user.roles = [
            RoleRow(role=r.role, scope_type=r.scope_type, scope_id=r.scope_id) for r in roles
        ]
        self.db.commit()
        return self.repo.get(id)

    def set_password(self, id: int, new_password: str) -> None:
        user = self.get(id)
        user.password_hash = hash_password(new_password)
        self.db.commit()

    def _validate(self, r: RoleAssignment) -> None:
        if r.scope_type == RoleScope.CLUB and r.scope_id is not None:
            raise ValidationError("Club roles have no scope_id")
        if r.scope_type == RoleScope.COHORT:
            CohortRepository(self.db).get_or_404(r.scope_id or 0)
        if r.scope_type == RoleScope.TEAM:
            ClubTeamRepository(self.db).get_or_404(r.scope_id or 0)
        if not self._can_grant(r):
            raise ForbiddenError(
                f"You can't grant {r.role.value} at {r.scope_type.value} scope there"
            )
