from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db, make_engine
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
