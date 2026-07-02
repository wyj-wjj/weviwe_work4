from typing import Any, Literal

from pydantic import BaseModel, Field


ContentImportType = Literal["base_script", "standard_script", "must_read"]
ContentImportParseMode = Literal["fast", "enhanced"]


class ImportSourceSpan(BaseModel):
    start_block: int = 0
    end_block: int = 0


class ImportDraft(BaseModel):
    title: str = ""
    category: str | None = None
    summary: str = ""
    body: str = ""
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ImportSplitSuggestion(ImportDraft):
    temp_id: str
    suggested_content_type: ContentImportType
    source_span: ImportSourceSpan = Field(default_factory=ImportSourceSpan)
    confidence: Literal["low", "medium", "high"] = "medium"
    validation_status: Literal["valid", "invalid", "warning"] = "valid"
    is_saveable: bool = True
    missing_fields: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)


class ImportPageInfo(BaseModel):
    page: int
    chosen: Literal["local", "ocr"]
    local_score: int
    ocr_score: int
    warning: str | None = None


class ImportParseTrace(BaseModel):
    file_type: Literal["docx", "pdf"]
    parse_method: str
    local_block_count: int = 0
    image_count: int = 0
    ocr_image_count: int = 0
    ocr_failed_count: int = 0
    ocr_page_count: int = 0
    structure_status: Literal["completed", "failed"] | None = None


class ContentImportResponse(BaseModel):
    content_type: ContentImportType
    single_draft: ImportDraft
    split_suggestions: list[ImportSplitSuggestion] = Field(default_factory=list)
    raw_text: str
    parse_method: str
    warnings: list[str] = Field(default_factory=list)
    pages: list[ImportPageInfo] = Field(default_factory=list)
    parse_trace: ImportParseTrace | None = None
    extraction_warnings: list[str] = Field(default_factory=list)
    structure_warnings: list[str] = Field(default_factory=list)
    structure_status: Literal["completed", "failed"] = "completed"
    structure_error_code: str | None = None
    structure_error_message: str | None = None
