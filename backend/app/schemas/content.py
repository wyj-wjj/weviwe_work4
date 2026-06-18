from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import ContentLevel, ContentType


class ContentCreate(BaseModel):
    content_type: ContentType
    title: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    permission_level: ContentLevel
    summary: str | None = None
    body: str = Field(min_length=1)
    structured_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_type_specific_payload(self) -> "ContentCreate":
        payload = self.structured_payload or {}
        if self.content_type == ContentType.STANDARD_SCRIPT and not payload.get("scene"):
            raise ValueError("standard_script requires structured_payload.scene")
        if self.content_type == ContentType.MUST_READ:
            if not payload.get("update_body") or not payload.get("adjustment_points"):
                raise ValueError("must_read requires update_body and adjustment_points")
        return self


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    permission_level: ContentLevel | None = None
    summary: str | None = None
    body: str | None = Field(default=None, min_length=1)
    structured_payload: dict[str, Any] | None = None


class ContentAdminOut(BaseModel):
    id: int
    content_type: str
    title: str
    category: str | None
    permission_level: str
    status: str
    current_version_id: int | None
    current_version_no: int | None
    index_status: str
    summary: str | None
    body: str
    structured_payload: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


class PaginatedContentOut(BaseModel):
    items: list[ContentAdminOut]
    total: int
    page: int
    page_size: int
