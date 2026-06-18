from sqlalchemy import select

from app.api.deps import get_dashscope_client, get_milvus_client
from app.domain.enums import ContentLevel, ContentType, MissedQuestionStatus
from app.integrations.dashscope import FakeDashScopeClient, ProviderTimeoutError
from app.integrations.milvus import FakeMilvusClient, MilvusSearchHit
from app.main import app
from app.models.missed_question import MissedQuestion
from app.models.user import User
from app.schemas.content import ContentCreate
from app.services.content_service import create_content, publish_content
from app.services.rag_answer_service import MISSED_MESSAGE, answer_question
from app.services.rag_index_service import sync_content_index


def make_user(db_session, *, username: str, account_type: str, content_level: str) -> User:
    user = User(
        username=username,
        password_hash="hash",
        display_name=username,
        account_type=account_type,
        content_level=content_level,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def publish_indexed_content(
    db_session,
    creator: User,
    *,
    title: str,
    body: str,
    permission_level: ContentLevel,
    milvus: FakeMilvusClient,
) -> tuple[int, int]:
    content = create_content(
        db_session,
        creator=creator,
        payload=ContentCreate(
            content_type=ContentType.BASE_SCRIPT,
            title=title,
            category="sales",
            permission_level=permission_level,
            body=body,
            structured_payload={"points": [body]},
        ),
    )
    publish_content(db_session, content_id=content.id)
    sync_content_index(
        db_session,
        content_id=content.id,
        dashscope_client=FakeDashScopeClient(embedding=[0.1, 0.2, 0.3]),
        milvus_client=milvus,
    )
    db_session.refresh(content)
    return content.id, content.current_version_id


def test_rag_filters_mixed_milvus_candidates_and_uses_only_authorized_context(db_session) -> None:
    admin = make_user(db_session, username="rag-admin", account_type="admin", content_level="full")
    general_user = make_user(db_session, username="rag-general", account_type="general_user", content_level="general")
    milvus = FakeMilvusClient()
    general_content_id, _ = publish_indexed_content(
        db_session,
        admin,
        title="General Greeting",
        body="Greet customers before asking questions.",
        permission_level=ContentLevel.GENERAL,
        milvus=milvus,
    )
    full_content_id, _ = publish_indexed_content(
        db_session,
        admin,
        title="Full Pricing",
        body="Full permission pricing policy.",
        permission_level=ContentLevel.FULL,
        milvus=milvus,
    )
    milvus.search_results = [
        MilvusSearchHit(primary_key="full", score=0.97, metadata={"content_id": full_content_id, "chunk_id": 2, "permission_level": "full", "is_active": True}),
        MilvusSearchHit(primary_key="general", score=0.95, metadata={"content_id": general_content_id, "chunk_id": 1, "permission_level": "general", "is_active": True}),
    ]
    dashscope = FakeDashScopeClient(chat_answer="Use the approved greeting.", embedding=[0.2, 0.2, 0.2])

    result = answer_question(
        db_session,
        user=general_user,
        question="How should I greet a customer?",
        dashscope_client=dashscope,
        milvus_client=milvus,
    )

    assert result["hit"] is True
    assert dashscope.embedding_requests == ["How should I greet a customer?"]
    assert milvus.search_requests[-1].allowed_permission_levels == {"general"}
    assert [source["content_id"] for source in result["sources"]] == [general_content_id]
    context_text = dashscope.chat_requests[-1]["contexts"][0]["text"]
    assert "Greet customers" in context_text
    assert "Full permission pricing policy" not in context_text


def test_rag_low_score_records_missed_question(db_session) -> None:
    user = make_user(db_session, username="missed-user", account_type="general_user", content_level="general")
    milvus = FakeMilvusClient(
        search_results=[
            MilvusSearchHit(
                primary_key="low-score",
                score=0.2,
                metadata={"content_id": 1, "chunk_id": 1, "permission_level": "general", "is_active": True},
            )
        ]
    )

    result = answer_question(
        db_session,
        user=user,
        question="Unanswerable question",
        dashscope_client=FakeDashScopeClient(embedding=[0.2, 0.2, 0.2]),
        milvus_client=milvus,
    )

    missed = db_session.scalars(select(MissedQuestion)).one()
    assert result == {"hit": False, "answer": MISSED_MESSAGE, "sources": []}
    assert missed.question == "Unanswerable question"
    assert missed.user_id == user.id
    assert missed.account_type == "general_user"
    assert missed.content_level == "general"
    assert missed.status == MissedQuestionStatus.NEW.value


def test_rag_api_covers_success_unauthorized_permission_filter_and_provider_error(
    client,
    admin_headers,
    general_user_headers,
    db_session,
) -> None:
    milvus = FakeMilvusClient()
    admin = db_session.scalars(select(User).where(User.username == "admin-user")).one()
    general_content_id, _ = publish_indexed_content(
        db_session,
        admin,
        title="API General",
        body="API visible general text.",
        permission_level=ContentLevel.GENERAL,
        milvus=milvus,
    )
    full_content_id, _ = publish_indexed_content(
        db_session,
        admin,
        title="API Full",
        body="API hidden full text.",
        permission_level=ContentLevel.FULL,
        milvus=milvus,
    )
    milvus.search_results = [
        MilvusSearchHit(primary_key="full", score=0.98, metadata={"content_id": full_content_id, "chunk_id": 2, "permission_level": "full", "is_active": True}),
        MilvusSearchHit(primary_key="general", score=0.96, metadata={"content_id": general_content_id, "chunk_id": 1, "permission_level": "general", "is_active": True}),
    ]
    dashscope = FakeDashScopeClient(chat_answer="API answer", embedding=[0.3, 0.3, 0.3])
    app.dependency_overrides[get_dashscope_client] = lambda: dashscope
    app.dependency_overrides[get_milvus_client] = lambda: milvus

    success = client.post("/api/app/rag/ask", json={"question": "api question"}, headers=general_user_headers)
    unauthorized = client.post("/api/app/rag/ask", json={"question": "api question"})

    assert success.status_code == 200
    assert success.json()["hit"] is True
    assert success.json()["sources"][0]["content_id"] == general_content_id
    assert "API hidden full text" not in str(dashscope.chat_requests[-1])
    assert unauthorized.status_code == 401

    app.dependency_overrides[get_dashscope_client] = lambda: FakeDashScopeClient(
        embedding=[0.3, 0.3, 0.3],
        chat_error=ProviderTimeoutError("chat timed out"),
    )
    unavailable = client.post("/api/app/rag/ask", json={"question": "api question"}, headers=general_user_headers)
    assert unavailable.status_code == 503
