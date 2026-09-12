"""Who can see and do what.

Roles live in `user_roles` at one of three scopes - club, cohort (age group) or team -
and widen upwards: a cohort coach can do everything a team coach can on every team in
the cohort. `Access` resolves a user's rows once per request into concrete team and
cohort permissions so services can ask simple questions.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError
from app.models import ClubTeam, Player, RoleScope, SquadMember, TeamSeason, User, UserRole

VIEWER, COACH, ADMIN = UserRole.VIEWER, UserRole.COACH, UserRole.ADMIN


def _max(*roles: UserRole | None) -> UserRole | None:
    present = [r for r in roles if r is not None]
    return max(present, key=lambda r: r.level) if present else None


@dataclass
class Access:
    user: User
    club_role: UserRole | None = None
    cohort_roles: dict[int, UserRole] = field(default_factory=dict)  # cohort_id -> role
    team_roles: dict[int, UserRole] = field(default_factory=dict)  # club_team_id -> role (direct)
    # Resolved: cohort of every team the user can reach, and every team id (None = all)
    _team_cohorts: dict[int, int] = field(default_factory=dict)  # club_team_id -> cohort_id

    # --- resolution ------------------------------------------------------------

    @classmethod
    def for_user(cls, db: Session, user: User) -> "Access":
        access = cls(user=user)
        for r in user.roles:
            role = UserRole(r.role)  # String column: coerce so .level works
            if r.scope_type == RoleScope.CLUB:
                access.club_role = _max(access.club_role, role)
            elif r.scope_type == RoleScope.COHORT:
                access.cohort_roles[r.scope_id] = _max(access.cohort_roles.get(r.scope_id), role)
            else:
                access.team_roles[r.scope_id] = _max(access.team_roles.get(r.scope_id), role)
        if access.club_role is None:
            ids = set(access.team_roles)
            stmt = select(ClubTeam.id, ClubTeam.cohort_id).where(
                ClubTeam.id.in_(ids) | ClubTeam.cohort_id.in_(access.cohort_roles.keys())
            )
            access._team_cohorts = {tid: cid for tid, cid in db.execute(stmt)}
        return access

    # --- questions --------------------------------------------------------------

    @property
    def is_club_admin(self) -> bool:
        return self.club_role == ADMIN

    @property
    def sees_everything(self) -> bool:
        return self.club_role is not None

    def visible_team_ids(self) -> set[int] | None:
        """None means every team."""
        return None if self.sees_everything else set(self._team_cohorts)

    def visible_cohort_ids(self) -> set[int] | None:
        if self.sees_everything:
            return None
        return set(self.cohort_roles) | set(self._team_cohorts.values())

    def role_for_team(self, team_id: int, cohort_id: int | None = None) -> UserRole | None:
        cohort_id = cohort_id if cohort_id is not None else self._team_cohorts.get(team_id)
        return _max(self.club_role, self.cohort_roles.get(cohort_id), self.team_roles.get(team_id))

    def role_for_cohort(self, cohort_id: int) -> UserRole | None:
        """Cohort-wide role only; a team coach has no cohort-level role."""
        return _max(self.club_role, self.cohort_roles.get(cohort_id))

    def can_view_cohort(self, cohort_id: int) -> bool:
        ids = self.visible_cohort_ids()
        return ids is None or cohort_id in ids

    # --- guards (raise 403) ------------------------------------------------------

    def require_team(self, team: ClubTeam, minimum: UserRole = VIEWER) -> UserRole:
        role = self.role_for_team(team.id, team.cohort_id)
        if role is None or role.level < minimum.level:
            raise ForbiddenError(f"You don't have {minimum.value} access to {team.name}")
        return role

    def require_team_season(self, ts: TeamSeason, minimum: UserRole = VIEWER) -> UserRole:
        return self.require_team(ts.club_team, minimum)

    def require_cohort(self, cohort_id: int, minimum: UserRole = VIEWER) -> UserRole:
        role = (
            self.role_for_cohort(cohort_id)
            if minimum.level > VIEWER.level
            else (
                self.role_for_cohort(cohort_id)
                or (VIEWER if self.can_view_cohort(cohort_id) else None)
            )
        )
        if role is None or role.level < minimum.level:
            raise ForbiddenError(f"You don't have {minimum.value} access to this age group")
        return role

    def require_club(self, minimum: UserRole = ADMIN) -> UserRole:
        if self.club_role is None or self.club_role.level < minimum.level:
            raise ForbiddenError("Club-level access required")
        return self.club_role

    def require_player(self, db: Session, player: Player, minimum: UserRole = VIEWER) -> UserRole:
        """Viewing: anyone in the player's cohort. Editing: coach+ on the cohort, or coach+
        on a team whose squad the player is in."""
        if self.sees_everything:
            return self.require_club(VIEWER)
        if player.cohort_id is None or not self.can_view_cohort(player.cohort_id):
            raise ForbiddenError("Player is not in your age group")
        if minimum.level <= VIEWER.level:
            return VIEWER
        cohort_role = self.role_for_cohort(player.cohort_id)
        if cohort_role is not None and cohort_role.level >= minimum.level:
            return cohort_role
        team_ids = set(
            db.scalars(
                select(TeamSeason.club_team_id)
                .join(SquadMember, SquadMember.team_season_id == TeamSeason.id)
                .where(SquadMember.player_id == player.id)
            )
        )
        best = _max(*(self.role_for_team(t) for t in team_ids))
        if best is None or best.level < minimum.level:
            raise ForbiddenError("Player is not in a squad you coach")
        return best
