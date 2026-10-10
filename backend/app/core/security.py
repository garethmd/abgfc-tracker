import hashlib
import secrets
from typing import NamedTuple

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_hasher = PasswordHasher()
SESSION_COOKIE = "abgfc_session"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """False for an account with no password at all (a parent, who uses email links)."""
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


# --- emailed single-use links ------------------------------------------------------


def new_login_token() -> tuple[str, str]:
    """(raw token for the email, sha256 hash to store). The raw value is never stored.

    Plain sha256 rather than argon2: the token is 256 bits from a CSPRNG, so there is
    nothing to brute-force, and verification is an indexed lookup by hash.
    """
    raw = secrets.token_urlsafe(32)
    return raw, hash_login_token(raw)


def hash_login_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# --- session cookie ----------------------------------------------------------------


class SessionClaims(NamedTuple):
    user_id: int
    # None for a cookie issued before session versions existed - still valid, see below.
    version: int | None


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="session")


def create_session_token(user_id: int, secret_key: str, session_version: int = 1) -> str:
    return _serializer(secret_key).dumps({"uid": user_id, "sv": session_version})


def read_session_token(token: str, secret_key: str, max_age: int) -> SessionClaims | None:
    """Cookies issued before `sv` existed carry no version and are accepted as they are:
    deploying this must not sign every coach out."""
    try:
        data = _serializer(secret_key).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid")
    if not isinstance(uid, int):
        return None
    version = data.get("sv")
    return SessionClaims(uid, version if isinstance(version, int) else None)
