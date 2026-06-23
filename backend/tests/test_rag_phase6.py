import pytest
from sqlalchemy import select

from app.api.deps import get_dashscope_client, get_milvus_client
from app.core.config import Settings
from app.domain.enums import ContentLevel, ContentType, MissedQuestionStatus
from app.integrations.dashscope import FakeDashScopeClient, ProviderTimeoutError
from app.integrations.milvus import FakeMilvusClient, MilvusSearchHit
from app.main import app
from app.models.content import ContentChunk
from app.models.missed_question import MissedQuestion
from app.models.user import User
from app.schemas.content import ContentCreate
from app.services.content_service import create_content, publish_content
from app.services.rag_answer_service import MISSED_MESSAGE, answer_question, load_authorized_contexts, retrieval_question
from app.services.rag_index_service import stable_content_hash, sync_content_index


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


def current_chunk(db_session, *, content_id: int) -> ContentChunk:
    return db_session.scalars(
        select(ContentChunk)
        .where(ContentChunk.content_id == content_id)
        .where(ContentChunk.is_active.is_(True))
        .order_by(ContentChunk.sort_order.asc(), ContentChunk.id.asc())
    ).one()


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
    general_chunk = current_chunk(db_session, content_id=general_content_id)
    full_chunk = current_chunk(db_session, content_id=full_content_id)
    milvus.search_results = [
        MilvusSearchHit(
            primary_key="full",
            score=0.97,
            metadata={
                "content_id": full_content_id,
                "chunk_id": full_chunk.id,
                "permission_level": "general",
                "is_active": True,
            },
        ),
        MilvusSearchHit(
            primary_key="general",
            score=0.95,
            metadata={
                "content_id": general_content_id,
                "chunk_id": general_chunk.id,
                "permission_level": "general",
                "is_active": True,
            },
        ),
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
    assert dashscope.chat_requests == []
    assert "Greet customers" in result["answer"]
    assert "Full permission pricing policy" not in result["answer"]


def test_rag_returns_fast_extractive_answer_without_waiting_for_chat_generation(db_session) -> None:
    admin = make_user(db_session, username="fast-admin", account_type="admin", content_level="full")
    general_user = make_user(db_session, username="fast-general", account_type="general_user", content_level="general")
    milvus = FakeMilvusClient()
    content_id, _ = publish_indexed_content(
        db_session,
        admin,
        title="Fast Safety Source",
        body="Fast approved safety answer should be returned from the authorized source.",
        permission_level=ContentLevel.GENERAL,
        milvus=milvus,
    )
    chunk = current_chunk(db_session, content_id=content_id)
    milvus.search_results = [
        MilvusSearchHit(
            primary_key="fast-source",
            score=0.92,
            metadata={
                "content_id": content_id,
                "chunk_id": chunk.id,
                "permission_level": "general",
                "is_active": True,
            },
        )
    ]
    dashscope = FakeDashScopeClient(
        embedding=[0.2, 0.2, 0.2],
        chat_error=ProviderTimeoutError("chat should not block fast answer"),
    )

    result = answer_question(
        db_session,
        user=general_user,
        question="How fast can this answer?",
        dashscope_client=dashscope,
        milvus_client=milvus,
    )

    assert result["hit"] is True
    assert "Fast approved safety answer" in result["answer"]
    assert result["sources"][0]["content_id"] == content_id
    assert dashscope.chat_requests == []


def test_environment_impact_short_question_expands_to_eia_terms() -> None:
    expanded = retrieval_question("项目环境影响")

    assert expanded.startswith("项目环境影响")
    assert "储能项目环境影响评价" in expanded
    assert "环评" in expanded


def test_hybrid_retrieval_uses_keyword_and_vector_results_together(db_session) -> None:
    admin = make_user(db_session, username="hybrid-admin", account_type="admin", content_level="full")
    general_user = make_user(db_session, username="hybrid-general", account_type="general_user", content_level="general")
    milvus = FakeMilvusClient()
    vector_content_id, _ = publish_indexed_content(
        db_session,
        admin,
        title="Vector Safety Source",
        body="Vector-only safety context should still be considered when it passes similarity.",
        permission_level=ContentLevel.GENERAL,
        milvus=milvus,
    )
    keyword_content_id, _ = publish_indexed_content(
        db_session,
        admin,
        title="储能消防配置基础话术",
        body="消防配置包括烟感、温感、气体灭火和消防验收资料。",
        permission_level=ContentLevel.GENERAL,
        milvus=milvus,
    )
    vector_chunk = current_chunk(db_session, content_id=vector_content_id)
    milvus.search_results = [
        MilvusSearchHit(
            primary_key="vector",
            score=0.86,
            metadata={
                "content_id": vector_content_id,
                "chunk_id": vector_chunk.id,
                "permission_level": "general",
                "is_active": True,
            },
        )
    ]
    dashscope = FakeDashScopeClient(embedding=[0.2, 0.2, 0.2])

    result = answer_question(
        db_session,
        user=general_user,
        question="消防相关话术",
        dashscope_client=dashscope,
        milvus_client=milvus,
    )

    source_ids = {source["content_id"] for source in result["sources"]}
    assert result["hit"] is True
    assert source_ids == {vector_content_id, keyword_content_id}
    assert "Vector-only safety context" in result["answer"]
    assert "消防配置包括烟感" in result["answer"]


def test_hybrid_keyword_retrieval_respects_user_permissions(db_session) -> None:
    admin = make_user(db_session, username="hybrid-permission-admin", account_type="admin", content_level="full")
    general_user = make_user(
        db_session,
        username="hybrid-permission-general",
        account_type="general_user",
        content_level="general",
    )
    milvus = FakeMilvusClient(search_results=[])
    publish_indexed_content(
        db_session,
        admin,
        title="全量消防配置内部话术",
        body="全量权限专属消防配置报价底线，不得泄露给通用权限员工。",
        permission_level=ContentLevel.FULL,
        milvus=milvus,
    )
    general_content_id, _ = publish_indexed_content(
        db_session,
        admin,
        title="通用消防配置基础话术",
        body="通用员工可见的消防配置说明。",
        permission_level=ContentLevel.GENERAL,
        milvus=milvus,
    )

    result = answer_question(
        db_session,
        user=general_user,
        question="消防配置话术",
        dashscope_client=FakeDashScopeClient(embedding=[0.2, 0.2, 0.2]),
        milvus_client=milvus,
        settings=Settings(rag_similarity_threshold=0.7),
    )

    assert result["hit"] is True
    assert [source["content_id"] for source in result["sources"]] == [general_content_id]
    assert "通用员工可见的消防配置说明" in result["answer"]
    assert "全量权限专属消防配置报价底线" not in result["answer"]


@pytest.mark.parametrize("question", ["电池能用多少次？", "这块电池能循环多少次？"])
def test_short_cycle_life_question_expands_only_embedding_text(db_session, question: str) -> None:
    admin = make_user(db_session, username="cycle-admin", account_type="admin", content_level="full")
    full_user = make_user(db_session, username="cycle-user", account_type="full_user", content_level="full")
    milvus = FakeMilvusClient()
    content_id, _ = publish_indexed_content(
        db_session,
        admin,
        title="电池循环寿命",
        body="电池设计循环寿命为 6000-8000 次。",
        permission_level=ContentLevel.FULL,
        milvus=milvus,
    )
    chunk = current_chunk(db_session, content_id=content_id)
    milvus.search_results = [
        MilvusSearchHit(
            primary_key="cycle",
            score=0.92,
            metadata={
                "content_id": content_id,
                "chunk_id": chunk.id,
                "permission_level": "full",
                "is_active": True,
            },
        )
    ]
    dashscope = FakeDashScopeClient(chat_answer="6000-8000 次", embedding=[1.0, 0.0, 0.0])

    result = answer_question(
        db_session,
        user=full_user,
        question=question,
        dashscope_client=dashscope,
        milvus_client=milvus,
    )

    assert result["hit"] is True
    assert dashscope.embedding_requests == [f"{question} 电池循环寿命 充放电循环次数"]
    assert dashscope.chat_requests == []


def test_short_cycle_life_miss_records_original_question(db_session) -> None:
    full_user = make_user(db_session, username="cycle-miss", account_type="full_user", content_level="full")
    dashscope = FakeDashScopeClient(embedding=[1.0, 0.0, 0.0])

    result = answer_question(
        db_session,
        user=full_user,
        question="电池能用多少次？",
        dashscope_client=dashscope,
        milvus_client=FakeMilvusClient(search_results=[]),
    )

    missed = db_session.scalars(select(MissedQuestion)).one()
    assert result["hit"] is False
    assert dashscope.embedding_requests == ["电池能用多少次？ 电池循环寿命 充放电循环次数"]
    assert missed.question == "电池能用多少次？"


def test_authorized_contexts_sort_by_score_and_drop_weak_relative_matches(db_session) -> None:
    admin = make_user(db_session, username="window-admin", account_type="admin", content_level="full")
    user = make_user(db_session, username="window-user", account_type="general_user", content_level="general")
    milvus = FakeMilvusClient()
    content_ids = [
        publish_indexed_content(
            db_session,
            admin,
            title=title,
            body=body,
            permission_level=ContentLevel.GENERAL,
            milvus=milvus,
        )[0]
        for title, body in [
            ("Best match", "Best approved context."),
            ("Second match", "Second approved context."),
            ("Weak match", "Weak approved context."),
        ]
    ]
    chunks = [current_chunk(db_session, content_id=content_id) for content_id in content_ids]
    hits = [
        MilvusSearchHit(
            primary_key="second",
            score=0.89,
            metadata={"chunk_id": chunks[1].id},
        ),
        MilvusSearchHit(
            primary_key="weak",
            score=0.71,
            metadata={"chunk_id": chunks[2].id},
        ),
        MilvusSearchHit(
            primary_key="best",
            score=0.91,
            metadata={"chunk_id": chunks[0].id},
        ),
    ]

    contexts = load_authorized_contexts(db_session, hits=hits, user=user, min_score=0.7)

    assert [context["source"]["content_id"] for context in contexts] == content_ids[:2]
    assert [context["source"]["relevance_score"] for context in contexts] == [0.91, 0.89]


def test_rag_merges_same_content_chunks_into_one_context_and_source(db_session) -> None:
    admin = make_user(db_session, username="merge-admin", account_type="admin", content_level="full")
    user = make_user(db_session, username="merge-user", account_type="general_user", content_level="general")
    milvus = FakeMilvusClient()
    content_id, version_id = publish_indexed_content(
        db_session,
        admin,
        title="Merged source",
        body="First approved section.",
        permission_level=ContentLevel.GENERAL,
        milvus=milvus,
    )
    first_chunk = current_chunk(db_session, content_id=content_id)
    second_text = "Second approved section."
    second_chunk = ContentChunk(
        content_id=content_id,
        version_id=version_id,
        chunk_type="base_script_body",
        chunk_text=second_text,
        sort_order=2,
        token_estimate=4,
        content_hash=stable_content_hash(second_text),
        permission_level=ContentLevel.GENERAL.value,
        is_active=True,
    )
    db_session.add(second_chunk)
    db_session.commit()
    db_session.refresh(second_chunk)
    milvus.search_results = [
        MilvusSearchHit(
            primary_key="first",
            score=0.91,
            metadata={
                "content_id": content_id,
                "chunk_id": first_chunk.id,
                "permission_level": "general",
                "is_active": True,
            },
        ),
        MilvusSearchHit(
            primary_key="second",
            score=0.89,
            metadata={
                "content_id": content_id,
                "chunk_id": second_chunk.id,
                "permission_level": "general",
                "is_active": True,
            },
        ),
    ]
    dashscope = FakeDashScopeClient(chat_answer="Merged answer", embedding=[0.2, 0.2, 0.2])

    result = answer_question(
        db_session,
        user=user,
        question="What is the approved source?",
        dashscope_client=dashscope,
        milvus_client=milvus,
    )

    assert result["hit"] is True
    assert len(result["sources"]) == 1
    assert dashscope.chat_requests == []
    assert "First approved section." in result["answer"]
    assert "Second approved section." in result["answer"]
    assert result["sources"][0]["chunk_id"] == first_chunk.id


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
    general_chunk = current_chunk(db_session, content_id=general_content_id)
    full_chunk = current_chunk(db_session, content_id=full_content_id)
    milvus.search_results = [
        MilvusSearchHit(
            primary_key="full",
            score=0.98,
            metadata={
                "content_id": full_content_id,
                "chunk_id": full_chunk.id,
                "permission_level": "full",
                "is_active": True,
            },
        ),
        MilvusSearchHit(
            primary_key="general",
            score=0.96,
            metadata={
                "content_id": general_content_id,
                "chunk_id": general_chunk.id,
                "permission_level": "general",
                "is_active": True,
            },
        ),
    ]
    dashscope = FakeDashScopeClient(chat_answer="API answer", embedding=[0.3, 0.3, 0.3])
    app.dependency_overrides[get_dashscope_client] = lambda: dashscope
    app.dependency_overrides[get_milvus_client] = lambda: milvus

    success = client.post("/api/app/rag/ask", json={"question": "api question"}, headers=general_user_headers)
    unauthorized = client.post("/api/app/rag/ask", json={"question": "api question"})

    assert success.status_code == 200
    assert success.json()["hit"] is True
    assert success.json()["sources"][0]["content_id"] == general_content_id
    assert dashscope.chat_requests == []
    assert "API hidden full text" not in success.json()["answer"]
    assert unauthorized.status_code == 401

    app.dependency_overrides[get_dashscope_client] = lambda: FakeDashScopeClient(
        embedding_error=ProviderTimeoutError("embedding timed out"),
    )
    unavailable = client.post("/api/app/rag/ask", json={"question": "api question"}, headers=general_user_headers)
    assert unavailable.status_code == 503
