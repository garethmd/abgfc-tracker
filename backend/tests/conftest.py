from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db, make_engine
from app.models import RoleScope, User, UserRole, UserRoleAssignment
from app.services.bootstrap import DemoSeason, seed_demo_season, seed_user


@pytest.fixture
def db() -> Generator[Session]:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def demo(db: Session) -> DemoSeason:
    d = seed_demo_season(db)
    db.commit()
    return d


@pytest.fixture
def client(db: Session) -> Generator[TestClient]:
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client: TestClient, db: Session) -> TestClient:
    seed_user(db, "coach", "secret")
    db.commit()
    r = client.post("/api/v1/auth/login", json={"username": "coach", "password": "secret"})
    assert r.status_code == 200, r.text
    return client


def make_user(db: Session, username: str, *roles: tuple[UserRole, RoleScope, int | None]) -> User:
    """Create a user with the given (role, scope, scope_id) rows; password = 'secret'."""
    user = User(username=username, password_hash=hash_password("secret"))
    user.roles = [UserRoleAssignment(role=r, scope_type=st, scope_id=sid) for r, st, sid in roles]
    db.add(user)
    db.commit()
    return user


def login_as(client: TestClient, username: str) -> TestClient:
    client.cookies.clear()
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "secret"})
    assert r.status_code == 200, r.text
    return client
