from app.core.security import verify_password
from app.models.user import User


def user_payload(**overrides):
    payload = {
        "username": "phase9-user",
        "password": "temporary-password",
        "display_name": "阶段九员工",
        "account_type": "general_user",
        "content_level": "general",
    }
    payload.update(overrides)
    return payload


def test_admin_can_create_list_edit_reset_disable_and_enable_users(client, admin_headers, db_session):
    created = client.post("/api/admin/users", json=user_payload(), headers=admin_headers)
    assert created.status_code == 201
    user_id = created.json()["id"]
    assert created.json()["is_active"] is True
    assert "password" not in created.json()
    assert "password_hash" not in created.json()

    listing = client.get("/api/admin/users?page=1&page_size=10", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 2
    listed = next(item for item in listing.json()["items"] if item["id"] == user_id)
    assert listed["username"] == "phase9-user"
    assert listed["updated_at"]

    edited = client.patch(
        f"/api/admin/users/{user_id}",
        json={
            "display_name": "阶段九完整权限员工",
            "account_type": "full_user",
            "content_level": "full",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["account_type"] == "full_user"
    assert edited.json()["content_level"] == "full"

    reset = client.post(
        f"/api/admin/users/{user_id}/reset-password",
        json={"password": "new-temporary-password"},
        headers=admin_headers,
    )
    assert reset.status_code == 200
    assert reset.json() == {"reset": True}
    db_session.expire_all()
    assert verify_password("new-temporary-password", db_session.get(User, user_id).password_hash)

    disabled = client.post(f"/api/admin/users/{user_id}/disable", headers=admin_headers)
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    login = client.post(
        "/api/auth/login",
        json={"username": "phase9-user", "password": "new-temporary-password"},
    )
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "account_disabled"

    enabled = client.post(f"/api/admin/users/{user_id}/enable", headers=admin_headers)
    assert enabled.status_code == 200
    assert enabled.json()["is_active"] is True

    relogin = client.post(
        "/api/auth/login",
        json={"username": "phase9-user", "password": "new-temporary-password"},
    )
    assert relogin.status_code == 200


def test_admin_user_management_rejects_duplicates_and_non_admins(
    client,
    admin_headers,
    general_user_headers,
):
    created = client.post("/api/admin/users", json=user_payload(), headers=admin_headers)
    assert created.status_code == 201

    duplicate = client.post("/api/admin/users", json=user_payload(), headers=admin_headers)
    assert duplicate.status_code == 409

    rejected = client.get("/api/admin/users", headers=general_user_headers)
    assert rejected.status_code == 403


def test_employee_account_management_cannot_create_or_promote_admin_accounts(client, admin_headers):
    create_admin = client.post(
        "/api/admin/users",
        json=user_payload(
            username="another-admin",
            account_type="admin",
            content_level="full",
        ),
        headers=admin_headers,
    )
    assert create_admin.status_code == 422

    created = client.post("/api/admin/users", json=user_payload(), headers=admin_headers)
    user_id = created.json()["id"]
    promote = client.patch(
        f"/api/admin/users/{user_id}",
        json={"account_type": "admin", "content_level": "full"},
        headers=admin_headers,
    )
    assert promote.status_code == 422
