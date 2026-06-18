from sqlalchemy import select

from app.domain.enums import ContentLevel, ContentType, IndexStatus
from app.integrations.dashscope import FakeDashScopeClient, ProviderTimeoutError
from app.integrations.milvus import FakeMilvusClient
from app.models.content import Content, ContentChunk, VectorIndexRecord
from app.models.user import User
from app.schemas.content import ContentCreate
from app.services.content_service import create_content, publish_content
from app.services.rag_index_service import stable_content_hash, sync_content_index


def create_content_payload(
    *,
    content_type: ContentType,
    title: str,
    permission_level: ContentLevel = ContentLevel.GENERAL,
    summary: str | None = None,
    body: str = "Approved body.",
    structured_payload: dict | None = None,
) -> ContentCreate:
    return ContentCreate(
        content_type=content_type,
        title=title,
        category="sales",
        permission_level=permission_level,
        summary=summary,
        body=body,
        structured_payload=structured_payload,
    )


def admin_user(db_session) -> User:
    admin = User(
        username="phase6-admin",
        password_hash="hash",
        display_name="Phase 6 Admin",
        account_type="admin",
        content_level="full",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def create_and_publish(db_session, creator: User, payload: ContentCreate) -> Content:
    content = create_content(db_session, creator=creator, payload=payload)
    publish_content(db_session, content_id=content.id)
    db_session.refresh(content)
    return content


def test_chunk_generation_rules_keep_metadata_and_business_boundaries(db_session) -> None:
    creator = admin_user(db_session)
    base = create_and_publish(
        db_session,
        creator,
        create_content_payload(
            content_type=ContentType.BASE_SCRIPT,
            title="Base",
            summary="Return calculation",
            body="Base approved text.",
            structured_payload={"points": ["IRR 12-15%", "回收期 3-5 年"]},
        ),
    )
    standard = create_and_publish(
        db_session,
        creator,
        create_content_payload(
            content_type=ContentType.STANDARD_SCRIPT,
            title="Scenario",
            summary="Price objection response",
            body="Fallback scenario body.",
            structured_payload={
                "scene": "Price objection",
                "recommended_speech": "Confirm value before discussing price.",
                "forbidden_speech": "Do not promise unavailable discounts.",
                "notes": "Keep the tone calm.",
            },
        ),
    )
    must_read = create_and_publish(
        db_session,
        creator,
        create_content_payload(
            content_type=ContentType.MUST_READ,
            title="Weekly Update",
            summary="Weekly policy changes",
            body="Read the weekly update.",
            structured_payload={
                "update_body": "Use the new greeting this week.",
                "adjustment_points": ["Confirm identity", "Ask for customer needs"],
            },
        ),
    )

    chunks = db_session.scalars(select(ContentChunk).order_by(ContentChunk.id.asc())).all()
    assert len(chunks) == 3
    for content in [base, standard, must_read]:
        chunk = next(item for item in chunks if item.content_id == content.id)
        assert chunk.version_id == content.current_version_id
        assert chunk.permission_level == content.permission_level
        assert chunk.is_active is True

    base_chunk = next(item for item in chunks if item.content_id == base.id)
    assert base_chunk.chunk_type == "base_script_body"
    assert "标题：Base" in base_chunk.chunk_text
    assert "分类：sales" in base_chunk.chunk_text
    assert "摘要：Return calculation" in base_chunk.chunk_text
    assert "正文：Base approved text." in base_chunk.chunk_text
    assert "要点：IRR 12-15%" in base_chunk.chunk_text
    assert "回收期 3-5 年" in base_chunk.chunk_text

    standard_chunk = next(item for item in chunks if item.content_id == standard.id)
    assert standard_chunk.chunk_type == "standard_script_scene"
    assert "标题：Scenario" in standard_chunk.chunk_text
    assert "分类：sales" in standard_chunk.chunk_text
    assert "摘要：Price objection response" in standard_chunk.chunk_text
    assert "场景：Price objection" in standard_chunk.chunk_text
    assert "推荐说法：Confirm value before discussing price." in standard_chunk.chunk_text
    assert "禁用说法：Do not promise unavailable discounts." in standard_chunk.chunk_text
    assert "注意事项：Keep the tone calm." in standard_chunk.chunk_text

    must_read_chunk = next(item for item in chunks if item.content_id == must_read.id)
    assert must_read_chunk.chunk_type == "must_read_update"
    assert "标题：Weekly Update" in must_read_chunk.chunk_text
    assert "分类：sales" in must_read_chunk.chunk_text
    assert "摘要：Weekly policy changes" in must_read_chunk.chunk_text
    assert "更新正文：Use the new greeting this week." in must_read_chunk.chunk_text
    assert "调整要点：Confirm identity" in must_read_chunk.chunk_text
    assert "Ask for customer needs" in must_read_chunk.chunk_text


def test_chunk_hash_is_stable_for_same_text_and_changes_when_text_changes() -> None:
    assert stable_content_hash("Same approved text.") == stable_content_hash("Same approved text.")
    assert stable_content_hash("Same approved text.") != stable_content_hash("Changed approved text.")


def test_index_sync_success_creates_active_vector_records(db_session) -> None:
    creator = admin_user(db_session)
    content = create_and_publish(
        db_session,
        creator,
        create_content_payload(
            content_type=ContentType.BASE_SCRIPT,
            title="Index Me",
            summary="Index summary.",
            body="Indexable text.",
        ),
    )
    dashscope = FakeDashScopeClient(embedding=[0.1, 0.2, 0.3], embedding_model="fake-embedding")
    milvus = FakeMilvusClient()

    result = sync_content_index(db_session, content_id=content.id, dashscope_client=dashscope, milvus_client=milvus)

    db_session.refresh(content)
    record = db_session.scalars(select(VectorIndexRecord).where(VectorIndexRecord.content_id == content.id)).one()
    assert result.status == IndexStatus.SYNCED.value
    assert content.index_status == IndexStatus.SYNCED.value
    assert record.milvus_primary_key.startswith("content-")
    assert record.embedding_model == "fake-embedding"
    assert record.embedding_dimension == 3
    assert record.is_active is True
    assert dashscope.embedding_requests == [
        "标题：Index Me\n分类：sales\n摘要：Index summary.\n正文：Indexable text."
    ]


def test_index_sync_failure_keeps_published_content_visible(client, db_session, general_user_headers) -> None:
    creator = admin_user(db_session)
    content = create_and_publish(
        db_session,
        creator,
        create_content_payload(content_type=ContentType.BASE_SCRIPT, title="Visible After Failure", body="Still visible."),
    )
    dashscope = FakeDashScopeClient(embedding_error=ProviderTimeoutError("slow provider"))

    result = sync_content_index(db_session, content_id=content.id, dashscope_client=dashscope, milvus_client=FakeMilvusClient())

    db_session.refresh(content)
    assert result.status == IndexStatus.FAILED.value
    assert content.index_status == IndexStatus.FAILED.value
    response = client.get(f"/api/app/scripts/{content.id}", headers=general_user_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Visible After Failure"


def test_admin_retry_index_turns_failed_status_to_synced(client, admin_headers, db_session) -> None:
    created = client.post(
        "/api/admin/contents",
        json={
            "content_type": "base_script",
            "title": "Retry Index",
            "category": "sales",
            "permission_level": "general",
            "body": "Retry this content.",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    content_id = created.json()["id"]
    published = client.post(f"/api/admin/contents/{content_id}/publish", headers=admin_headers)
    assert published.status_code == 200

    content = db_session.get(Content, content_id)
    content.index_status = IndexStatus.FAILED.value
    db_session.commit()

    retried = client.post(f"/api/admin/contents/{content_id}/retry-index", headers=admin_headers)

    assert retried.status_code == 200
    assert retried.json()["index_status"] == IndexStatus.SYNCED.value
