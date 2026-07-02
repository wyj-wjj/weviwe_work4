from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError
from app.integrations.dashscope import normalize_provider_error
from app.schemas.content_import import ContentImportResponse, ImportPageInfo
from app.services.document_extractors import extract_docx, extract_pdf
from app.services.document_structuring_service import structure_import_result


SUPPORTED_EXTENSIONS = {".docx", ".pdf"}
SUPPORTED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf",
    "application/octet-stream",
}


@dataclass(frozen=True)
class ImportFile:
    file_name: str
    content_type: str | None
    data: bytes


def parse_content_import(
    *,
    upload: ImportFile,
    content_type: str,
    parse_mode: str,
    force_ocr: bool,
    dashscope_client,
    settings: Settings | None = None,
) -> ContentImportResponse:
    resolved_settings = settings or Settings()
    _validate_file(upload, settings=resolved_settings)
    effective_parse_mode = parse_mode or resolved_settings.content_import_default_parse_mode
    if effective_parse_mode not in {"fast", "enhanced"}:
        raise AppError(code="invalid_parse_mode", message="解析模式不支持。", status_code=422)

    extension = Path(upload.file_name).suffix.lower()
    try:
        if extension == ".docx":
            extracted = extract_docx(
                upload.data,
                content_type=content_type,
                dashscope_client=dashscope_client,
                force_ocr=force_ocr,
            )
        else:
            extracted = extract_pdf(
                upload.data,
                content_type=content_type,
                parse_mode=effective_parse_mode,
                force_ocr=force_ocr,
                dashscope_client=dashscope_client,
                settings=resolved_settings,
            )
        structured = structure_import_result(
            dashscope_client=dashscope_client,
            content_type=content_type,
            file_name=upload.file_name,
            parse_mode=effective_parse_mode,
            raw_text=extracted.raw_text,
            warnings=extracted.warnings,
        )
    except AppError:
        raise
    except Exception as exc:
        provider_error = normalize_provider_error(exc)
        if provider_error.code.startswith("provider_"):
            raise AppError(code=provider_error.code, message=provider_error.message, status_code=503) from exc
        raise

    single_draft = structured.single_draft
    split_suggestions = structured.split_suggestions
    structure_warnings = list(structured.warnings or single_draft.warnings)
    warnings = [*extracted.warnings, *structure_warnings]
    parse_trace = dict(extracted.parse_trace or {})
    if parse_trace:
        parse_trace["structure_status"] = structured.status
    return ContentImportResponse(
        content_type=content_type,
        single_draft=single_draft,
        split_suggestions=split_suggestions,
        raw_text=extracted.raw_text,
        parse_method=extracted.parse_method,
        warnings=warnings,
        extraction_warnings=extracted.warnings,
        structure_warnings=structure_warnings,
        structure_status=structured.status,
        structure_error_code=structured.error_code,
        structure_error_message=structured.error_message,
        parse_trace=parse_trace or None,
        pages=[
            ImportPageInfo(
                page=page.page,
                chosen=page.chosen,
                local_score=page.local_score,
                ocr_score=page.ocr_score,
                warning=page.warning,
            )
            for page in extracted.pages
        ],
    )


def _validate_file(upload: ImportFile, *, settings: Settings) -> None:
    extension = Path(upload.file_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        if extension == ".doc":
            raise AppError(
                code="unsupported_file_type",
                message="仅支持 Word docx 和 PDF 文件；老版 .doc 请另存为 .docx 后上传。",
                status_code=422,
            )
        raise AppError(code="unsupported_file_type", message="仅支持 Word docx 和 PDF 文件。", status_code=422)
    if upload.content_type and upload.content_type not in SUPPORTED_MIME_TYPES:
        raise AppError(code="unsupported_file_type", message="仅支持 Word docx 和 PDF 文件。", status_code=422)
    max_bytes = settings.content_import_max_file_mb * 1024 * 1024
    if len(upload.data) > max_bytes:
        raise AppError(code="file_too_large", message="文件过大，请拆分后上传。", status_code=413)
    if not upload.data:
        raise AppError(code="empty_document", message="未识别到有效文本，请检查文件。", status_code=422)
