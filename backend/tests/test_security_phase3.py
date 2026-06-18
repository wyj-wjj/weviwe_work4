from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_differs_from_plaintext_and_verifies_original_password() -> None:
    password = "local-test-password"

    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_access_token_round_trip_and_expiry() -> None:
    token = create_access_token(
        subject="42",
        account_type="admin",
        content_level="full",
        expires_delta=timedelta(minutes=5),
    )

    payload = decode_access_token(token)

    assert payload.subject == "42"
    assert payload.account_type == "admin"
    assert payload.content_level == "full"

    expired_token = create_access_token(
        subject="42",
        account_type="admin",
        content_level="full",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="expired"):
        decode_access_token(expired_token)
