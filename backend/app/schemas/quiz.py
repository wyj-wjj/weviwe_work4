from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import ContentLevel, QuestionStatus


class QuizQuestionCreate(BaseModel):
    question: str = Field(min_length=1)
    options: list[Any] = Field(min_length=2)
    answer: str = Field(min_length=1)
    explanation: str | None = None
    related_content_id: int | None = None
    permission_level: ContentLevel
    status: QuestionStatus = QuestionStatus.ENABLED


class QuizQuestionUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    options: list[Any] | None = Field(default=None, min_length=2)
    answer: str | None = Field(default=None, min_length=1)
    explanation: str | None = None
    related_content_id: int | None = None
    permission_level: ContentLevel | None = None
    status: QuestionStatus | None = None


class QuizSubmitAnswer(BaseModel):
    question_id: int
    selected_answer: str


class QuizSubmitRequest(BaseModel):
    answers: list[QuizSubmitAnswer] = Field(min_length=1, max_length=10)
