from app.cli.create_admin import upsert_initial_admin
from app.core.security import verify_password


def test_initial_admin_cli_creates_and_updates_a_hashed_admin(db_session) -> None:
    created = upsert_initial_admin(
        db_session,
        username="local-admin",
        password="first-secure-password",
        display_name="本地管理员",
    )

    assert created.username == "local-admin"
    assert created.display_name == "本地管理员"
    assert created.account_type == "admin"
    assert created.content_level == "full"
    assert created.is_active is True
    assert created.password_hash != "first-secure-password"
    assert verify_password("first-secure-password", created.password_hash)

    updated = upsert_initial_admin(
        db_session,
        username="local-admin",
        password="second-secure-password",
        display_name="更新后的管理员",
    )

    assert updated.id == created.id
    assert updated.display_name == "更新后的管理员"
    assert verify_password("second-secure-password", updated.password_hash)
