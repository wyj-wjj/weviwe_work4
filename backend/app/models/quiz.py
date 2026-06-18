from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ContentLevel, QuestionStatus
from app.models.base import Base, TimestampMixin


class QuizQuestion(TimestampMixin, Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        CheckConstraint(
            f"permission_level in {tuple(item.value for item in ContentLevel)}",
            name="ck_quiz_questions_permission_level",
        ),
        CheckConstraint(
            f"status in {tuple(item.value for item in QuestionStatus)}",
            name="ck_quiz_questions_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    answer: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    related_content_id: Mapped[int | None] = mapped_column(ForeignKey("contents.id"))
    permission_level: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=QuestionStatus.ENABLED.value)

    related_content = relationship("Content")
