from typing import Any

from pydantic import BaseModel, Field

from datetime import datetime

from app.domain.enums import ContentLevel, QuestionStatus, QuizReviewStatus, QuizSourceType


class QuizQuestionCreate(BaseModel):
    question: str = Field(min_length=1)
    options: list[Any] = Field(min_length=2)
    answer: str = Field(min_length=1)
    explanation: str | None = None
    related_content_id: int | None = None
    related_version_id: int | None = None
    permission_level: ContentLevel
    status: QuestionStatus = QuestionStatus.ENABLED
    source_type: QuizSourceType = QuizSourceType.MANUAL
    review_status: QuizReviewStatus = QuizReviewStatus.APPROVED
    generation_batch_id: int | None = None
    needs_review: bool = False
    review_reason: str | None = None
    expires_at: datetime | None = None
    priority: int = 0


class QuizQuestionUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    options: list[Any] | None = Field(default=None, min_length=2)
    answer: str | None = Field(default=None, min_length=1)
    explanation: str | None = None
    related_content_id: int | None = None
    related_version_id: int | None = None
    permission_level: ContentLevel | None = None
    status: QuestionStatus | None = None
    source_type: QuizSourceType | None = None
    review_status: QuizReviewStatus | None = None
    generation_batch_id: int | None = None
    needs_review: bool | None = None
    review_reason: str | None = None
    expires_at: datetime | None = None
    priority: int | None = None


class QuizGenerateRequest(BaseModel):
    requested_count: int | None = Field(default=None, ge=1, le=10)
    create_quiz_set: bool = True


class QuizSubmitAnswer(BaseModel):
    question_id: int
    selected_answer: str


class QuizSubmitRequest(BaseModel):
    answers: list[QuizSubmitAnswer] = Field(min_length=1, max_length=10)
