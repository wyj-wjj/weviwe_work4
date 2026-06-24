from typing import Any

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    ContentLevel,
    QuestionStatus,
    QuizGenerationStatus,
    QuizReviewStatus,
    QuizSetStatus,
    QuizSourceType,
    UpdateLevel,
)
from app.models.base import Base, TimestampMixin, utc_now


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
        CheckConstraint(
            f"source_type in {tuple(item.value for item in QuizSourceType)}",
            name="ck_quiz_questions_source_type",
        ),
        CheckConstraint(
            f"review_status in {tuple(item.value for item in QuizReviewStatus)}",
            name="ck_quiz_questions_review_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    answer: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    related_content_id: Mapped[int | None] = mapped_column(ForeignKey("contents.id"))
    related_version_id: Mapped[int | None] = mapped_column(ForeignKey("content_versions.id"))
    permission_level: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=QuestionStatus.ENABLED.value)
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=QuizSourceType.MANUAL.value,
        server_default=QuizSourceType.MANUAL.value,
    )
    review_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=QuizReviewStatus.APPROVED.value,
        server_default=QuizReviewStatus.APPROVED.value,
    )
    generation_batch_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_generation_batches.id"), index=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    review_reason: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    related_content = relationship("Content")
    related_version = relationship("ContentVersion")
    generation_batch = relationship("QuizGenerationBatch", back_populates="questions")
    set_items = relationship("QuizQuestionSetItem", back_populates="question")


class QuizGenerationBatch(Base):
    __tablename__ = "quiz_generation_batches"
    __table_args__ = (
        CheckConstraint(
            f"update_level in {tuple(item.value for item in UpdateLevel)}",
            name="ck_quiz_generation_batches_update_level",
        ),
        CheckConstraint(
            f"status in {tuple(item.value for item in QuizGenerationStatus)}",
            name="ck_quiz_generation_batches_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), nullable=False, index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("content_versions.id"), nullable=False, index=True)
    update_level: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=QuizGenerationStatus.PENDING.value,
        server_default=QuizGenerationStatus.PENDING.value,
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    content = relationship("Content")
    version = relationship("ContentVersion")
    creator = relationship("User")
    questions = relationship("QuizQuestion", back_populates="generation_batch")


class QuizSet(Base):
    __tablename__ = "quiz_sets"
    __table_args__ = (
        CheckConstraint(
            f"update_level in {tuple(item.value for item in UpdateLevel)}",
            name="ck_quiz_sets_update_level",
        ),
        CheckConstraint(
            f"permission_level in {tuple(item.value for item in ContentLevel)}",
            name="ck_quiz_sets_permission_level",
        ),
        CheckConstraint(
            f"status in {tuple(item.value for item in QuizSetStatus)}",
            name="ck_quiz_sets_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    related_content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), nullable=False, index=True)
    related_version_id: Mapped[int] = mapped_column(ForeignKey("content_versions.id"), nullable=False, index=True)
    update_level: Mapped[str] = mapped_column(String(32), nullable=False)
    permission_level: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=QuizSetStatus.ACTIVE.value,
        server_default=QuizSetStatus.ACTIVE.value,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    related_content = relationship("Content")
    related_version = relationship("ContentVersion")
    items = relationship("QuizQuestionSetItem", back_populates="quiz_set", cascade="all, delete-orphan")


class QuizQuestionSetItem(Base):
    __tablename__ = "quiz_question_set_items"

    quiz_set_id: Mapped[int] = mapped_column(ForeignKey("quiz_sets.id"), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    quiz_set = relationship("QuizSet", back_populates="items")
    question = relationship("QuizQuestion", back_populates="set_items")
