from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_hasher = PasswordHasher()
SESSION_COOKIE = "abgfc_session"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="session")


def create_session_token(user_id: int, secret_key: str) -> str:
    return _serializer(secret_key).dumps({"uid": user_id})


def read_session_token(token: str, secret_key: str, max_age: int) -> int | None:
    try:
        data = _serializer(secret_key).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("uid")
