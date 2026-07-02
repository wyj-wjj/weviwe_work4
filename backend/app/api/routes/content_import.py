from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_dashscope_client, require_admin
from app.core.errors import AppError
from app.domain.enums import ContentType
from app.schemas.content_import import ContentImportResponse
from app.services.document_import_service import ImportFile, parse_content_import


router = APIRouter(tags=["content-import"])


@router.post("/api/admin/content-import/parse")
async def admin_parse_content_import(
    content_type: str = Form(...),
    parse_mode: str = Form("fast"),
    force_ocr: bool = Form(False),
    file: UploadFile = File(...),
    _admin=Depends(require_admin),
    dashscope_client=Depends(get_dashscope_client),
) -> dict[str, Any]:
    if content_type not in {item.value for item in ContentType}:
        raise AppError(code="invalid_content_type", message="内容类型不支持。", status_code=422)
    if content_type not in {
        ContentType.BASE_SCRIPT.value,
        ContentType.STANDARD_SCRIPT.value,
        ContentType.MUST_READ.value,
    }:
        raise AppError(code="invalid_content_type", message="内容类型不支持。", status_code=422)
    result: ContentImportResponse = parse_content_import(
        upload=ImportFile(
            file_name=file.filename or "upload",
            content_type=file.content_type,
            data=await file.read(),
        ),
        content_type=content_type,
        parse_mode=parse_mode,
        force_ocr=force_ocr,
        dashscope_client=dashscope_client,
    )
    return result.model_dump()
