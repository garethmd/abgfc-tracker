from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Passkey(TimestampMixin, Base):
    """A WebAuthn credential - what a parent signs in with instead of a password.

    We store only the **public** key. There is no shared secret here at all: a copy of
    this table is useless to an attacker, and the credential is bound to our domain, so
    a convincing fake of the site cannot ask for it. Several per user is normal and
    encouraged (phone and laptop), so losing one device doesn't mean losing the account.
    """

    __tablename__ = "passkeys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Raw credential id as the authenticator returned it; unique across every account.
    credential_id: Mapped[bytes] = mapped_column(LargeBinary(1024), unique=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary(1024))
    # Counts signatures where the authenticator keeps one. A value that fails to climb
    # hints at a cloned authenticator; we log it rather than lock anyone out.
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    # "iPhone", "Jo's laptop" - so a coach or parent can tell two credentials apart.
    label: Mapped[str | None] = mapped_column(String(100))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="passkeys")


class WebAuthnChallenge(Base):
    """A one-shot challenge for a passkey ceremony.

    Kept server-side rather than handed to the client, so a challenge issued for
    registration can never be replayed as an authentication (OWASP's passkey guidance
    is explicit about binding ceremony type, account and expiry). Consumed by deleting
    the row, so a second attempt with the same challenge matches nothing.
    """

    __tablename__ = "webauthn_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge: Mapped[bytes] = mapped_column(LargeBinary(128), unique=True)
    # "register" | "authenticate"
    purpose: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
