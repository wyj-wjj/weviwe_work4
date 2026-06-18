import pytest
from pydantic import ValidationError

from app.domain.enums import AccountType, ContentLevel
from app.schemas.user import UserCreate


def test_invalid_account_type_is_rejected_before_database_write() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            username="bad-role",
            password="local-password",
            display_name="错误角色",
            account_type="manager",
            content_level=ContentLevel.GENERAL,
        )


def test_invalid_content_level_is_rejected_before_database_write() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            username="bad-level",
            password="local-password",
            display_name="错误级别",
            account_type=AccountType.GENERAL_USER,
            content_level="private",
        )
