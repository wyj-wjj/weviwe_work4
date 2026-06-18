from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import AccountType, ContentLevel, MissedQuestionStatus
from app.models.base import Base, utc_now


class MissedQuestion(Base):
    __tablename__ = "missed_questions"
    __table_args__ = (
        CheckConstraint(
            f"account_type in {tuple(item.value for item in AccountType)}",
            name="ck_missed_questions_account_type",
        ),
        CheckConstraint(
            f"content_level in {tuple(item.value for item in ContentLevel)}",
            name="ck_missed_questions_content_level",
        ),
        CheckConstraint(
            f"status in {tuple(item.value for item in MissedQuestionStatus)}",
            name="ck_missed_questions_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_level: Mapped[str] = mapped_column(String(32), nullable=False)
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=MissedQuestionStatus.NEW.value, nullable=False)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="missed_questions")
