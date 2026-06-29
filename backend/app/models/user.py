from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import AccountType, ContentLevel
from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            f"account_type in {tuple(item.value for item in AccountType)}",
            name="ck_users_account_type",
        ),
        CheckConstraint(
            f"content_level in {tuple(item.value for item in ContentLevel)}",
            name="ck_users_content_level",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_level: Mapped[str] = mapped_column(String(32), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    department = relationship("Department", back_populates="users", foreign_keys=[department_id])
    created_contents = relationship("Content", back_populates="creator", foreign_keys="Content.created_by")
    created_versions = relationship("ContentVersion", back_populates="creator", foreign_keys="ContentVersion.created_by")
    missed_questions = relationship("MissedQuestion", back_populates="user")
