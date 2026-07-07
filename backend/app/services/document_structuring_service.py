from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.integrations.dashscope import normalize_provider_error
from app.schemas.content_import import ImportDraft, ImportSourceSpan, ImportSplitSuggestion


SUMMARY_MAX_CHARS = 500
STRUCTURE_FALLBACK_WARNING = (
    "AI 结构化失败；已使用本地解析文本生成保守草稿，请人工核对字段。"
)
HEADING_PATTERNS = (
    re.compile(r"^\d+(?:\.\d+)+\s*\S+"),
    re.compile(r"^第[一二三四五六七八九十百]+部分[:：]\s*\S+"),
    re.compile(r"^[一二三四五六七八九十]+[、.]\s*\S+"),
    re.compile(r"^[（(]\d+[）)]\s*\S+"),
)

IMPORT_CONTENT_FIELD_CONTRACTS: dict[str, dict[str, Any]] = {
    "must_read": {
        "label": "最新必读",
        "required_top_level_fields": ["title", "summary", "body"],
        "required_payload_fields": ["update_body"],
        "recommended_payload_fields": ["adjustment_points"],
        "split_allowed": False,
    },
    "base_script": {
        "label": "核心基础话术",
        "required_top_level_fields": ["title", "summary", "body"],
        "required_payload_fields": [],
        "recommended_payload_fields": ["points"],
        "split_allowed": True,
    },
    "standard_script": {
        "label": "标准化话术",
        "required_top_level_fields": ["title", "summary", "body"],
        "required_payload_fields": ["scene", "recommended_speech"],
        "recommended_payload_fields": ["forbidden_speech", "notes"],
        "split_allowed": True,
    },
}

FIELD_LABELS = {
    "title": "标题",
    "summary": "摘要",
    "body": "正文",
    "update_body": "更新正文",
    "adjustment_points": "调整要点",
    "points": "核心要点",
    "scene": "场景",
    "recommended_speech": "推荐说法",
    "forbidden_speech": "禁用说法",
    "notes": "注意事项",
}


@dataclass(frozen=True)
class StructuringResult:
    single_draft: ImportDraft
    split_suggestions: list[ImportSplitSuggestion]
    status: str = "completed"
    warnings: list[str] | None = None
    error_code: str | None = None
    error_message: str | None = None


def structure_import_result(
    *,
    dashscope_client,
    content_type: str,
    file_name: str,
    parse_mode: str,
    raw_text: str,
    warnings: list[str],
) -> tuple[ImportDraft, list[ImportSplitSuggestion]]:
    try:
        raw_response = dashscope_client.structure_content_import(
            content_type=content_type,
            file_name=file_name,
            parse_mode=parse_mode,
            raw_text=raw_text,
            warnings=warnings,
        )
        data = json.loads(raw_response)
    except Exception:
        single_draft = fallback_import_draft(content_type=content_type, file_name=file_name, raw_text=raw_text)
        single_draft.warnings.append("AI 结构化失败，已使用本地解析文本生成保守草稿，请人工核对字段。")
        return single_draft, suggest_split_suggestions(
            raw_text=raw_text,
            content_type=content_type,
            single_draft=single_draft,
        )
    if not isinstance(data, dict):
        single_draft = fallback_import_draft(content_type=content_type, file_name=file_name, raw_text=raw_text)
        single_draft.warnings.append("AI 结构化失败，已使用本地解析文本生成保守草稿，请人工核对字段。")
        return single_draft, suggest_split_suggestions(
            raw_text=raw_text,
            content_type=content_type,
            single_draft=single_draft,
        )

    single_draft = normalize_import_draft(
        data,
        content_type=content_type,
        file_name=file_name,
        raw_text=raw_text,
    )
    split_suggestions = normalize_split_suggestions(
        data.get("split_suggestions"),
        fallback_content_type=content_type,
        raw_text=raw_text,
    )
    if not split_suggestions:
        split_suggestions = suggest_split_suggestions(
            raw_text=raw_text,
            content_type=content_type,
            single_draft=single_draft,
        )
    return single_draft, split_suggestions


def fallback_import_draft(
    *,
    content_type: str,
    file_name: str,
    raw_text: str,
) -> ImportDraft:
    return ImportDraft(
        title=Path(file_name).stem or "导入草稿",
        category=None,
        summary=_truncate(_first_non_empty_text(raw_text), SUMMARY_MAX_CHARS),
        body=raw_text,
        structured_payload=normalize_structured_payload({}, content_type=content_type),
        warnings=[],
    )


def normalize_import_draft(
    value: dict[str, Any],
    *,
    content_type: str,
    file_name: str,
    raw_text: str,
) -> ImportDraft:
    title = _string(value.get("title")) or Path(file_name).stem or "导入草稿"
    summary = _truncate(_string(value.get("summary")), SUMMARY_MAX_CHARS)
    body = _string(value.get("body")) or raw_text
    category = _string(value.get("category")) or None
    warnings = _string_list(value.get("warnings"))
    structured_payload = normalize_structured_payload(value.get("structured_payload"), content_type=content_type)
    return ImportDraft(
        title=title,
        category=category,
        summary=summary,
        body=body,
        structured_payload=structured_payload,
        warnings=warnings,
    )


def normalize_structured_payload(value: Any, *, content_type: str) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    if content_type == "standard_script":
        return {
            "scene": _string(payload.get("scene")),
            "recommended_speech": _string(payload.get("recommended_speech")),
            "forbidden_speech": _string(payload.get("forbidden_speech")),
            "notes": _string(payload.get("notes")),
        }
    if content_type == "must_read":
        return {
            "update_body": _string(payload.get("update_body")),
            "adjustment_points": _string_list(payload.get("adjustment_points")),
        }
    return {
        "points": _string_list(payload.get("points")),
    }


def normalize_split_suggestions(
    value: Any,
    *,
    fallback_content_type: str,
    raw_text: str,
) -> list[ImportSplitSuggestion]:
    if not _split_allowed(fallback_content_type):
        return []
    if not isinstance(value, list):
        return []
    suggestions: list[ImportSplitSuggestion] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        suggested_type = item.get("suggested_content_type")
        if suggested_type not in {"base_script", "standard_script", "must_read"}:
            suggested_type = fallback_content_type
        draft = normalize_import_draft(
            item,
            content_type=str(suggested_type),
            file_name=f"draft-{index}",
            raw_text=_string(item.get("body")) or raw_text,
        )
        source_span = item.get("source_span") if isinstance(item.get("source_span"), dict) else {}
        confidence = item.get("confidence")
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"
        suggestions.append(
            ImportSplitSuggestion(
                **draft.model_dump(),
                temp_id=_string(item.get("temp_id")) or f"draft-{index}",
                suggested_content_type=suggested_type,
                source_span=ImportSourceSpan(
                    start_block=_int(source_span.get("start_block"), 0),
                    end_block=_int(source_span.get("end_block"), 0),
                ),
                confidence=confidence,
            )
        )
    return finalize_split_suggestions(suggestions)


def suggest_split_suggestions(
    *,
    raw_text: str,
    content_type: str,
    single_draft: ImportDraft,
) -> list[ImportSplitSuggestion]:
    if not _split_allowed(content_type):
        return []
    if len(raw_text) < 1800:
        return []
    sections = conservative_sections(raw_text)
    meaningful_sections = [section for section in sections if len(section) > 120]
    if len(meaningful_sections) < 2:
        return []
    suggestions: list[ImportSplitSuggestion] = []
    for index, section in enumerate(meaningful_sections, start=1):
        title = section.splitlines()[0].strip()[:80] if section.splitlines() else f"{single_draft.title} {index}"
        if len(section) < 300 and suggestions:
            previous = suggestions[-1]
            previous.body = f"{previous.body}\n\n{section}".strip()
            previous.source_span.end_block = index
            previous.warnings.append("该候选由短片段保守合并，请确认边界。")
            continue
        suggestions.append(
            ImportSplitSuggestion(
                temp_id=f"draft-{index}",
                suggested_content_type=content_type,
                title=title or single_draft.title,
                category=single_draft.category,
                summary="",
                body=section,
                structured_payload=normalize_structured_payload({}, content_type=content_type),
                source_span=ImportSourceSpan(start_block=index, end_block=index),
                confidence="medium",
                warnings=[],
            )
        )
    return finalize_split_suggestions(suggestions)


def conservative_sections(raw_text: str) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if _looks_like_heading(stripped) and current:
            sections.append("\n".join(current).strip())
            current = [stripped]
        else:
            current.append(stripped)
    if current:
        sections.append("\n".join(current).strip())
    return [section for section in sections if section.strip()]


def _looks_like_heading(value: str) -> bool:
    if not value:
        return False
    return any(pattern.match(value) for pattern in HEADING_PATTERNS) or value.endswith(("：", ":"))


def finalize_split_suggestions(suggestions: list[ImportSplitSuggestion]) -> list[ImportSplitSuggestion]:
    repair_tail_headings(suggestions)
    for suggestion in suggestions:
        apply_split_validation(suggestion)
    return suggestions


def repair_tail_headings(suggestions: list[ImportSplitSuggestion]) -> None:
    for index, suggestion in enumerate(suggestions):
        lines = suggestion.body.splitlines()
        if not lines:
            continue
        tail = lines[-1].strip()
        if not _looks_like_heading(tail):
            continue
        if index + 1 >= len(suggestions):
            _append_unique(suggestion.quality_warnings, "块尾疑似残留下一节标题，请人工核对。")
            continue
        next_suggestion = suggestions[index + 1]
        suggestion.body = "\n".join(lines[:-1]).strip()
        next_suggestion.body = f"{tail}\n{next_suggestion.body}".strip()
        _append_unique(next_suggestion.quality_warnings, "标题边界已自动修正，请核对上下文。")


def apply_split_validation(suggestion: ImportSplitSuggestion) -> None:
    contract = IMPORT_CONTENT_FIELD_CONTRACTS.get(suggestion.suggested_content_type, {})
    missing_fields: list[str] = []
    warning_fields: list[str] = []

    for field_name in contract.get("required_top_level_fields", []):
        if _is_blank(getattr(suggestion, field_name, None)):
            missing_fields.append(FIELD_LABELS.get(field_name, field_name))
    payload = suggestion.structured_payload or {}
    for field_name in contract.get("required_payload_fields", []):
        if _is_blank(payload.get(field_name)):
            missing_fields.append(FIELD_LABELS.get(field_name, field_name))
    for field_name in contract.get("recommended_payload_fields", []):
        if _is_blank(payload.get(field_name)):
            warning_fields.append(FIELD_LABELS.get(field_name, field_name))

    existing_quality_warnings = list(suggestion.quality_warnings)
    for label in warning_fields:
        _append_unique(existing_quality_warnings, f"{label}为空，请人工核对。")

    suggestion.missing_fields = missing_fields
    suggestion.quality_warnings = existing_quality_warnings
    if missing_fields:
        suggestion.validation_status = "invalid"
        suggestion.is_saveable = False
    elif suggestion.quality_warnings:
        suggestion.validation_status = "warning"
        suggestion.is_saveable = True
    else:
        suggestion.validation_status = "valid"
        suggestion.is_saveable = True


def _split_allowed(content_type: str) -> bool:
    return bool(IMPORT_CONTENT_FIELD_CONTRACTS.get(content_type, {}).get("split_allowed"))


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not [item for item in value if not _is_blank(item)]
    return False


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def _truncate(value: str, max_chars: int) -> str:
    return value[:max_chars].rstrip() if len(value) > max_chars else value


def _first_non_empty_text(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return "\n".join(lines[:3]) if lines else ""


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _failed_structure_result(
    *,
    exc: Exception,
    content_type: str,
    file_name: str,
    raw_text: str,
) -> StructuringResult:
    provider_error = normalize_provider_error(exc)
    single_draft = fallback_import_draft(content_type=content_type, file_name=file_name, raw_text=raw_text)
    single_draft.warnings.append(STRUCTURE_FALLBACK_WARNING)
    return StructuringResult(
        single_draft=single_draft,
        split_suggestions=suggest_split_suggestions(
            raw_text=raw_text,
            content_type=content_type,
            single_draft=single_draft,
        ),
        status="failed",
        warnings=[STRUCTURE_FALLBACK_WARNING],
        error_code=provider_error.code,
        error_message=provider_error.message,
    )


def structure_import_result(
    *,
    dashscope_client,
    content_type: str,
    file_name: str,
    parse_mode: str,
    raw_text: str,
    warnings: list[str],
) -> StructuringResult:
    try:
        raw_response = dashscope_client.structure_content_import(
            content_type=content_type,
            file_name=file_name,
            parse_mode=parse_mode,
            raw_text=raw_text,
            warnings=warnings,
        )
        data = json.loads(raw_response)
        if not isinstance(data, dict):
            raise ValueError("AI structure response must be a JSON object.")
    except Exception as exc:
        return _failed_structure_result(
            exc=exc,
            content_type=content_type,
            file_name=file_name,
            raw_text=raw_text,
        )

    single_draft = normalize_import_draft(
        data,
        content_type=content_type,
        file_name=file_name,
        raw_text=raw_text,
    )
    split_suggestions = normalize_split_suggestions(
        data.get("split_suggestions"),
        fallback_content_type=content_type,
        raw_text=raw_text,
    )
    if not split_suggestions:
        split_suggestions = suggest_split_suggestions(
            raw_text=raw_text,
            content_type=content_type,
            single_draft=single_draft,
        )
    return StructuringResult(
        single_draft=single_draft,
        split_suggestions=split_suggestions,
        status="completed",
        warnings=list(single_draft.warnings),
    )
