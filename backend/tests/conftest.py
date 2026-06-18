from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User


@pytest.fixture()
def sqlite_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture()
def db_session(sqlite_url: str) -> Generator[Session, None, None]:
    engine = create_engine(sqlite_url)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create_test_user(
    db_session: Session,
    *,
    username: str,
    account_type: str,
    content_level: str,
    password: str = "password",
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=f"{username} 显示名",
        account_type=account_type,
        content_level=content_level,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_headers(client: TestClient, username: str, password: str = "password") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    create_test_user(db_session, username="admin-user", account_type="admin", content_level="full")
    return auth_headers(client, "admin-user")


@pytest.fixture()
def full_user_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    create_test_user(db_session, username="full-user", account_type="full_user", content_level="full")
    return auth_headers(client, "full-user")


@pytest.fixture()
def general_user_headers(client: TestClient, db_session: Session) -> dict[str, str]:
    create_test_user(db_session, username="general-user", account_type="general_user", content_level="general")
    return auth_headers(client, "general-user")
