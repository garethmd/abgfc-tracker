from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.player import PlayerGuardian
from app.models.enums import RoleScope, check_in
from app.models.enums import UserRole as Role


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True)
    # Parents sign in with an emailed link and have no password at all; coaches have a
    # password and (today) no email. Either column alone identifies an account.
    email: Mapped[str | None] = mapped_column(String(255), unique=True)  # lowercased
    display_name: Mapped[str | None] = mapped_column(String(100))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # Bumped to sign every device out without deactivating the account. Cookies issued
    # before this existed carry no version and stay valid - see core/security.py.
    session_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    guardian_of: Mapped[list["PlayerGuardian"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_parent(self) -> bool:
        return bool(self.guardian_of)


class UserRole(Base):
    """What a user may do, and where. Scope widens: team < cohort < club.
    Stuart (age-group coach) = one row with scope cohort; a team coach = scope team."""

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "scope_type", "scope_id"),
        CheckConstraint(check_in("role", Role), name="role"),
        CheckConstraint(check_in("scope_type", RoleScope), name="scope_type"),
        CheckConstraint(
            "(scope_type = 'club' AND scope_id IS NULL) "
            "OR (scope_type <> 'club' AND scope_id IS NOT NULL)",
            name="scope_id_presence",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[Role] = mapped_column(String(20))
    scope_type: Mapped[RoleScope] = mapped_column(String(20))
    scope_id: Mapped[int | None] = mapped_column(Integer)  # cohort id or club_team id

    user: Mapped[User] = relationship(back_populates="roles")
