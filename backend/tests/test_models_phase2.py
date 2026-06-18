import pytest
from sqlalchemy import exc

from app.domain.enums import ContentLevel, ContentStatus, ContentType, QuestionStatus
from app.models.content import Content, ContentChunk, ContentVersion, VectorIndexRecord
from app.models.missed_question import MissedQuestion
from app.models.quiz import QuizQuestion
from app.models.user import User


def test_user_table_requires_unique_usernames(db_session) -> None:
    first = User(
        username="duplicate",
        password_hash="hash-one",
        display_name="用户一",
        account_type="general_user",
        content_level="general",
    )
    second = User(
        username="duplicate",
        password_hash="hash-two",
        display_name="用户二",
        account_type="full_user",
        content_level="full",
    )

    db_session.add_all([first, second])

    with pytest.raises(exc.IntegrityError):
        db_session.commit()


def test_content_version_chunk_and_vector_records_keep_required_relationships(db_session) -> None:
    creator = User(
        username="admin-fixture",
        password_hash="hash",
        display_name="管理员",
        account_type="admin",
        content_level="full",
    )
    content = Content(
        content_type=ContentType.BASE_SCRIPT.value,
        title="通用接待话术",
        category="接待",
        permission_level=ContentLevel.GENERAL.value,
        status=ContentStatus.PUBLISHED.value,
        creator=creator,
    )
    version = ContentVersion(
        content=content,
        version_no=1,
        title="通用接待话术",
        summary="接待时保持一致口径",
        body="请使用统一问候语。",
        structured_payload={"points": ["问候", "确认需求"]},
        creator=creator,
    )
    content.current_version = version
    chunk = ContentChunk(
        content=content,
        version=version,
        chunk_type="body",
        chunk_text="请使用统一问候语。",
        sort_order=1,
        token_estimate=12,
        content_hash="hash-body",
        permission_level=ContentLevel.GENERAL.value,
    )
    vector = VectorIndexRecord(
        content=content,
        version=version,
        chunk=chunk,
        milvus_collection="weview_scripts",
        milvus_primary_key="chunk-1",
        embedding_model="text-embedding-v4",
        embedding_dimension=1024,
        content_hash="hash-body",
    )

    db_session.add(vector)
    db_session.commit()

    assert content.current_version_id == version.id
    assert chunk.content_id == content.id
    assert chunk.version_id == version.id
    assert vector.chunk_id == chunk.id


def test_version_numbers_are_unique_per_content_item(db_session) -> None:
    creator = User(
        username="admin-version",
        password_hash="hash",
        display_name="管理员",
        account_type="admin",
        content_level="full",
    )
    content = Content(
        content_type=ContentType.MUST_READ.value,
        title="最新更新",
        category="公告",
        permission_level=ContentLevel.FULL.value,
        status=ContentStatus.DRAFT.value,
        creator=creator,
    )
    db_session.add_all(
        [
            ContentVersion(content=content, version_no=1, title="v1", body="正文", creator=creator),
            ContentVersion(content=content, version_no=1, title="v1 again", body="正文", creator=creator),
        ]
    )

    with pytest.raises(exc.IntegrityError):
        db_session.commit()


def test_quiz_questions_and_missed_questions_keep_permission_snapshots(db_session) -> None:
    user = User(
        username="general-user",
        password_hash="hash",
        display_name="通用用户",
        account_type="general_user",
        content_level="general",
    )
    quiz = QuizQuestion(
        question="遇到客户询问时应先做什么？",
        options=["确认需求", "直接报价"],
        answer="确认需求",
        explanation="先确认需求再推荐。",
        permission_level=ContentLevel.GENERAL.value,
        status=QuestionStatus.ENABLED.value,
    )
    missed = MissedQuestion(
        question="这个问题没有命中",
        user=user,
        account_type=user.account_type,
        content_level=user.content_level,
    )

    db_session.add_all([quiz, missed])
    db_session.commit()

    assert quiz.permission_level == "general"
    assert quiz.status == "enabled"
    assert missed.account_type == "general_user"
    assert missed.content_level == "general"
