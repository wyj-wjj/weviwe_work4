import pytest

from app.api.deps import ensure_content_visible, permitted_content_levels
from app.core.errors import AppError
from app.domain.enums import AccountType, ContentLevel
from app.models.user import User


def make_user(account_type: str, content_level: str) -> User:
    return User(
        username=f"{account_type}-{content_level}",
        password_hash="hash",
        display_name="测试用户",
        account_type=account_type,
        content_level=content_level,
    )


def test_content_level_filter_helper_matches_account_permissions() -> None:
    general_user = make_user(AccountType.GENERAL_USER.value, ContentLevel.GENERAL.value)
    full_user = make_user(AccountType.FULL_USER.value, ContentLevel.FULL.value)
    admin = make_user(AccountType.ADMIN.value, ContentLevel.FULL.value)

    assert permitted_content_levels(general_user) == {ContentLevel.GENERAL.value}
    assert permitted_content_levels(full_user) == {ContentLevel.GENERAL.value, ContentLevel.FULL.value}
    assert permitted_content_levels(admin) == {ContentLevel.GENERAL.value, ContentLevel.FULL.value}


def test_permission_denied_error_does_not_leak_content_fields() -> None:
    general_user = make_user(AccountType.GENERAL_USER.value, ContentLevel.GENERAL.value)

    with pytest.raises(AppError) as exc_info:
        ensure_content_visible(general_user, ContentLevel.FULL.value)

    error = exc_info.value
    assert error.status_code == 403
    assert error.code == "permission_denied"
    assert error.message == "无权查看该内容"
    assert error.details is None
    assert "标题" not in error.message
    assert "正文" not in error.message
