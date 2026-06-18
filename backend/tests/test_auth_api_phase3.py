from app.core.security import hash_password
from app.models.user import User


def add_user(db_session, *, username: str, password: str, account_type: str, content_level: str, is_active: bool = True) -> User:
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


def test_login_returns_identity_account_type_content_level_and_access_token(client, db_session) -> None:
    add_user(
        db_session,
        username="admin-login",
        password="correct-password",
        account_type="admin",
        content_level="full",
    )

    response = client.post(
        "/api/auth/login",
        json={"username": "admin-login", "password": "correct-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["username"] == "admin-login"
    assert payload["user"]["account_type"] == "admin"
    assert payload["user"]["content_level"] == "full"
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"


def test_login_failures_do_not_reveal_whether_username_password_or_status_failed(client, db_session) -> None:
    add_user(
        db_session,
        username="disabled-user",
        password="correct-password",
        account_type="general_user",
        content_level="general",
        is_active=False,
    )

    responses = [
        client.post("/api/auth/login", json={"username": "missing-user", "password": "anything"}),
        client.post("/api/auth/login", json={"username": "disabled-user", "password": "correct-password"}),
        client.post("/api/auth/login", json={"username": "disabled-user", "password": "wrong-password"}),
    ]

    for response in responses:
        assert response.status_code == 401
        assert response.json() == {
            "error": {
                "code": "invalid_credentials",
                "message": "用户名或密码错误。",
                "details": None,
            }
        }


def test_current_user_dependency_rejects_missing_token_and_accepts_valid_token(client, db_session) -> None:
    add_user(
        db_session,
        username="full-user",
        password="correct-password",
        account_type="full_user",
        content_level="full",
    )

    unauthenticated = client.get("/api/auth/me")
    assert unauthenticated.status_code == 401

    login_response = client.post(
        "/api/auth/login",
        json={"username": "full-user", "password": "correct-password"},
    )
    token = login_response.json()["access_token"]

    authenticated = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert authenticated.status_code == 200
    assert authenticated.json()["username"] == "full-user"


def test_admin_dependency_rejects_employee_accounts_and_allows_admin(client, db_session) -> None:
    add_user(
        db_session,
        username="general-route-user",
        password="password",
        account_type="general_user",
        content_level="general",
    )
    add_user(
        db_session,
        username="admin-route-user",
        password="password",
        account_type="admin",
        content_level="full",
    )

    general_token = client.post(
        "/api/auth/login",
        json={"username": "general-route-user", "password": "password"},
    ).json()["access_token"]
    admin_token = client.post(
        "/api/auth/login",
        json={"username": "admin-route-user", "password": "password"},
    ).json()["access_token"]

    rejected = client.get("/api/admin/ping", headers={"Authorization": f"Bearer {general_token}"})
    allowed = client.get("/api/admin/ping", headers={"Authorization": f"Bearer {admin_token}"})

    assert rejected.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json() == {"status": "ok"}
