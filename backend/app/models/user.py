from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import RoleScope, check_in
from app.models.enums import UserRole as Role


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


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
