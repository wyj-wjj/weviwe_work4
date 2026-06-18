import os
from getpass import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.domain.enums import AccountType, ContentLevel
from app.models.user import User


def upsert_initial_admin(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str,
) -> User:
    normalized_username = username.strip()
    normalized_display_name = display_name.strip()
    if not normalized_username:
        raise ValueError("管理员用户名不能为空。")
    if not normalized_display_name:
        raise ValueError("管理员展示名不能为空。")
    if len(password) < 8:
        raise ValueError("管理员密码至少需要 8 位。")

    user = db.scalar(select(User).where(User.username == normalized_username))
    if user is None:
        user = User(username=normalized_username)
        db.add(user)
    user.display_name = normalized_display_name
    user.password_hash = hash_password(password)
    user.account_type = AccountType.ADMIN.value
    user.content_level = ContentLevel.FULL.value
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


def main() -> None:
    username = os.getenv("INITIAL_ADMIN_USERNAME") or input("管理员用户名: ").strip()
    display_name = os.getenv("INITIAL_ADMIN_DISPLAY_NAME") or input("管理员展示名: ").strip()
    password = os.getenv("INITIAL_ADMIN_PASSWORD") or getpass("管理员密码（至少 8 位）: ")
    with SessionLocal() as session:
        admin = upsert_initial_admin(
            session,
            username=username,
            password=password,
            display_name=display_name,
        )
    print(f"管理员账号已就绪：{admin.username}（id={admin.id}）")


if __name__ == "__main__":
    main()
