from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import InputModel, ORMModel


class PasskeyRead(ORMModel):
    id: int
    label: str
    created_at: datetime
    last_used_at: datetime | None


class PasskeyRegister(InputModel):
    """The browser's PublicKeyCredential, serialised. Verified in full server-side."""

    credential: dict[str, Any]
    label: str | None = Field(default=None, max_length=100)


class PasskeyAuthenticate(InputModel):
    credential: dict[str, Any]


class SigninOptions(ORMModel):
    """What a parent can use to get in - the sign-in page asks before offering anything."""

    passkeys: bool  # any passkey registered at all
    email_links: bool  # emailed links still permitted
