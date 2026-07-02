import io
import json
import zipfile

import pytest
from sqlalchemy import func, select

from app.api.deps import get_dashscope_client
from app.integrations.dashscope import ProviderResponseError, ProviderTimeoutError
from app.main import app
from app.models.content import Content, ContentChunk, VectorIndexRecord


class ImportFakeDashScopeClient:
    def __init__(
        self,
        *,
        ocr_text: str = "图片 OCR 识别文字",
        ocr_error: Exception | None = None,
        structure_payload: dict | str | None = None,
        structure_error: Exception | None = None,
    ) -> None:
        self.ocr_text = ocr_text
        self.ocr_error = ocr_error
        self.structure_payload = structure_payload or {
            "title": "导入标题",
            "category": "导入分类",
            "summary": "导入摘要",
            "body": "导入正文",
            "structured_payload": {"points": ["导入要点"]},
            "warnings": [],
            "split_suggestions": [],
        }
        self.structure_error = structure_error
        self.ocr_requests: list[dict] = []
        self.structure_requests: list[dict] = []

    def ocr_image(self, *, image_bytes: bytes, mime_type: str) -> str:
        self.ocr_requests.append({"size": len(image_bytes), "mime_type": mime_type})
        if self.ocr_error is not None:
            raise self.ocr_error
        return self.ocr_text

    def structure_content_import(self, **payload) -> str:
        self.structure_requests.append(payload)
        if self.structure_error is not None:
            raise self.structure_error
        if isinstance(self.structure_payload, str):
            return self.structure_payload
        return json.dumps(self.structure_payload, ensure_ascii=False)


def make_docx_bytes(*, include_image: bool = False) -> bytes:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:r><w:t>第一段：客户先说明需求。</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>场景</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>推荐说法</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>价格异议</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>先解释价值</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:p><w:r><w:t>最后一段：需要管理员核对。</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    package_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdImage1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
</Relationships>"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", package_rels)
        archive.writestr("word/document.xml", document_xml)
        if include_image:
            archive.writestr("word/_rels/document.xml.rels", document_rels)
            archive.writestr("word/media/image1.png", b"\x89PNG\r\n\x1a\n" + b"0" * 4096)
    return buffer.getvalue()


def make_pdf_bytes(page_texts: list[str]) -> bytes:
    import fitz

    document = fitz.open()
    for page_text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), page_text)
    return document.tobytes()


def test_content_import_requires_admin(client, general_user_headers):
    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script"},
        files={
            "file": (
                "sample.docx",
                make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=general_user_headers,
    )

    assert response.status_code == 403


def test_content_import_rejects_unsupported_file_types(client, admin_headers):
    doc_response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script"},
        files={"file": ("legacy.doc", b"legacy", "application/msword")},
        headers=admin_headers,
    )
    txt_response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script"},
        files={"file": ("notes.txt", b"text", "text/plain")},
        headers=admin_headers,
    )

    assert doc_response.status_code == 422
    assert doc_response.json()["error"]["code"] == "unsupported_file_type"
    assert "docx" in doc_response.json()["error"]["message"]
    assert txt_response.status_code == 422
    assert txt_response.json()["error"]["code"] == "unsupported_file_type"


def test_content_import_docx_parses_text_table_and_returns_single_draft_without_creating_content(
    client,
    admin_headers,
    db_session,
):
    fake = ImportFakeDashScopeClient(
        structure_payload={
            "title": "客户价格异议标准话术",
            "category": "价格口径",
            "summary": "围绕价格异议的回复摘要。",
            "body": "保留原文正文。",
            "structured_payload": {
                "scene": "客户质疑价格偏高",
                "recommended_speech": "先解释价值",
                "forbidden_speech": "不要直接降价",
                "notes": "核对数字",
            },
            "warnings": ["未识别到完整禁用说法，请管理员补充。"],
            "split_suggestions": [],
        }
    )
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "standard_script", "parse_mode": "fast"},
        files={
            "file": (
                "standard.docx",
                make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_type"] == "standard_script"
    assert payload["parse_method"] == "docx_local"
    assert "第一段：客户先说明需求。" in payload["raw_text"]
    assert "场景 | 推荐说法" in payload["raw_text"]
    assert payload["single_draft"]["title"] == "客户价格异议标准话术"
    assert payload["single_draft"]["structured_payload"] == {
        "scene": "客户质疑价格偏高",
        "recommended_speech": "先解释价值",
        "forbidden_speech": "不要直接降价",
        "notes": "核对数字",
    }
    assert payload["split_suggestions"] == []
    assert fake.structure_requests[0]["content_type"] == "standard_script"
    assert db_session.scalar(select(func.count()).select_from(Content)) == 0
    assert db_session.scalar(select(func.count()).select_from(ContentChunk)) == 0
    assert db_session.scalar(select(func.count()).select_from(VectorIndexRecord)) == 0


def test_content_import_docx_image_uses_ocr_and_reports_warning(client, admin_headers):
    fake = ImportFakeDashScopeClient(ocr_text="截图中的补充话术")
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script", "force_ocr": "true"},
        files={
            "file": (
                "image.docx",
                make_docx_bytes(include_image=True),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert fake.ocr_requests
    assert "截图中的补充话术" in payload["raw_text"]
    assert payload["parse_method"] == "docx_hybrid_ocr"
    assert any("图片 OCR" in warning for warning in payload["warnings"])


@pytest.mark.skip(reason="DOCX images are OCR'd by default after import stabilization.")
def test_content_import_docx_fast_mode_skips_image_ocr_when_local_text_exists(client, admin_headers):
    fake = ImportFakeDashScopeClient(ocr_error=ProviderResponseError("OCR failed."))
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script"},
        files={
            "file": (
                "image-ocr-failed.docx",
                make_docx_bytes(include_image=True),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert fake.ocr_requests == []
    assert "第一段：客户先说明需求。" in payload["raw_text"]
    assert payload["parse_method"] == "docx_local"
    assert any("快速解析未执行图片 OCR" in warning for warning in payload["warnings"])


def test_content_import_docx_fast_mode_ocr_images_even_when_local_text_exists(client, admin_headers):
    fake = ImportFakeDashScopeClient(ocr_text="image OCR supplemental text")
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script"},
        files={
            "file": (
                "image-fast.docx",
                make_docx_bytes(include_image=True),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(fake.ocr_requests) == 1
    assert "image OCR supplemental text" in payload["raw_text"]
    assert payload["parse_method"] == "docx_local_image_ocr"
    assert payload["parse_trace"] == {
        "file_type": "docx",
        "parse_method": "docx_local_image_ocr",
        "local_block_count": 3,
        "image_count": 1,
        "ocr_image_count": 1,
        "ocr_failed_count": 0,
        "ocr_page_count": 0,
        "structure_status": "completed",
    }


def test_content_import_docx_image_ocr_failure_keeps_local_text_and_trace(client, admin_headers):
    fake = ImportFakeDashScopeClient(ocr_error=ProviderResponseError("OCR failed."))
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script"},
        files={
            "file": (
                "image-ocr-failed.docx",
                make_docx_bytes(include_image=True),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(fake.ocr_requests) == 1
    assert payload["parse_method"] == "docx_local"
    assert payload["parse_trace"]["image_count"] == 1
    assert payload["parse_trace"]["ocr_image_count"] == 0
    assert payload["parse_trace"]["ocr_failed_count"] == 1
    assert payload["raw_text"]
    assert any("OCR" in warning for warning in payload["warnings"])


def test_content_import_pdf_enhanced_runs_ocr_for_each_page_and_returns_page_status(
    client,
    admin_headers,
):
    fake = ImportFakeDashScopeClient(ocr_text="OCR 更新内容：请核对数字 2026")
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "must_read", "parse_mode": "enhanced"},
        files={"file": ("must-read.pdf", make_pdf_bytes(["更新内容第一页", "调整要点第二页"]), "application/pdf")},
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parse_method"] == "pdf_hybrid_enhanced"
    assert len(fake.ocr_requests) == 2
    assert [page["page"] for page in payload["pages"]] == [1, 2]
    assert all(page["ocr_score"] > 0 for page in payload["pages"])
    assert payload["single_draft"]["structured_payload"]["update_body"] == ""
    assert "更新内容第一页" in payload["raw_text"] or "OCR 更新内容" in payload["raw_text"]


def test_content_import_invalid_structuring_response_reports_failure_status(client, admin_headers):
    app.dependency_overrides[get_dashscope_client] = lambda: ImportFakeDashScopeClient(structure_payload="{")

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script"},
        files={
            "file": (
                "broken-status.docx",
                make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["single_draft"]["title"] == "broken-status"
    assert payload["structure_status"] == "failed"
    assert payload["structure_error_code"] == "provider_response_invalid"
    assert payload["parse_trace"]["structure_status"] == "failed"


def test_content_import_structuring_timeout_reports_failure_status(client, admin_headers):
    fake = ImportFakeDashScopeClient(structure_error=ProviderTimeoutError("slow"))
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script"},
        files={
            "file": (
                "timeout.docx",
                make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["single_draft"]["title"] == "timeout"
    assert payload["structure_status"] == "failed"
    assert payload["structure_error_code"] == "provider_timeout"
    assert payload["structure_error_message"] == "Provider timed out."


def test_content_import_invalid_structuring_response_returns_fallback_draft(
    client,
    admin_headers,
):
    app.dependency_overrides[get_dashscope_client] = lambda: ImportFakeDashScopeClient(structure_payload="{")

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "base_script"},
        files={
            "file": (
                "broken.docx",
                make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["single_draft"]["title"] == "broken"
    assert "第一段：客户先说明需求。" in payload["single_draft"]["body"]
    assert any("AI 结构化失败" in warning for warning in payload["warnings"])


def test_content_import_standard_script_split_suggestion_reports_missing_required_fields(
    client,
    admin_headers,
):
    fake = ImportFakeDashScopeClient(
        structure_payload={
            "title": "Token 电池文档",
            "summary": "摘要",
            "body": "正文",
            "structured_payload": {},
            "warnings": [],
            "split_suggestions": [
                {
                    "temp_id": "draft-1",
                    "suggested_content_type": "standard_script",
                    "title": "缺字段候选",
                    "summary": "摘要",
                    "body": "正文",
                    "structured_payload": {
                        "scene": "",
                        "recommended_speech": "",
                        "forbidden_speech": "",
                        "notes": "",
                    },
                    "source_span": {"start_block": 1, "end_block": 2},
                    "confidence": "high",
                    "warnings": [],
                }
            ],
        }
    )
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "standard_script"},
        files={
            "file": (
                "token.docx",
                make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    suggestion = response.json()["split_suggestions"][0]
    assert suggestion["validation_status"] == "invalid"
    assert suggestion["is_saveable"] is False
    assert "场景" in suggestion["missing_fields"]
    assert "推荐说法" in suggestion["missing_fields"]


def test_content_import_repairs_tail_heading_in_split_suggestions(
    client,
    admin_headers,
):
    fake = ImportFakeDashScopeClient(
        structure_payload={
            "title": "Token 电池文档",
            "summary": "摘要",
            "body": "正文",
            "structured_payload": {},
            "warnings": [],
            "split_suggestions": [
                {
                    "temp_id": "draft-1",
                    "suggested_content_type": "standard_script",
                    "title": "第一块",
                    "summary": "摘要",
                    "body": "第一块正文\n1.7 为什么风光绿电直连是国家给出的最佳答案",
                    "structured_payload": {
                        "scene": "AI 算力中心用电",
                        "recommended_speech": "先解释绿电直连价值。",
                    },
                    "source_span": {"start_block": 1, "end_block": 2},
                    "confidence": "high",
                    "warnings": [],
                },
                {
                    "temp_id": "draft-2",
                    "suggested_content_type": "standard_script",
                    "title": "第二块",
                    "summary": "摘要",
                    "body": "第二块正文",
                    "structured_payload": {
                        "scene": "绿电直连",
                        "recommended_speech": "说明稳定供电。",
                    },
                    "source_span": {"start_block": 3, "end_block": 4},
                    "confidence": "high",
                    "warnings": [],
                },
            ],
        }
    )
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    response = client.post(
        "/api/admin/content-import/parse",
        data={"content_type": "standard_script"},
        files={
            "file": (
                "token.docx",
                make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    first, second = response.json()["split_suggestions"][:2]
    assert not first["body"].rstrip().endswith("最佳答案")
    assert second["body"].startswith("1.7 为什么风光绿电直连是国家给出的最佳答案")
    assert any("标题边界" in warning for warning in second["quality_warnings"])
