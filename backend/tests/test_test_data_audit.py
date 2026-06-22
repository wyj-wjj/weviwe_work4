import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli.audit_test_data import audit_test_data, classify_title
from app.domain.enums import (
    AccountType,
    ContentLevel,
    ContentStatus,
    ContentType,
    MissedQuestionStatus,
    QuestionStatus,
)
from app.models.content import Content, ContentChunk, ContentVersion, VectorIndexRecord
from app.models.missed_question import MissedQuestion
from app.models.quiz import QuizQuestion
from app.models.user import User


def test_audit_matches_only_known_test_records() -> None:
    assert classify_title("Phase45 Must Read General") == "phase45"
    assert classify_title("阶段8手测：基础开场白") == "phase8"
    assert classify_title("阶段8手测题 1：应该怎么做？") == "phase8"
    assert classify_title("E2E 通用最新必读") == "e2e"
    assert classify_title("??8??????") == "mojibake"

    assert classify_title("客户正式业务话术") is None
    assert classify_title("阶段8业务复盘") is None
    assert classify_title("Phase450 客户方案") is None
    assert classify_title("??8客户正式业务话术") is None


def test_audit_defaults_to_dry_run_and_leaves_rows_unchanged(db_session: Session) -> None:
    fixture = _seed_audit_fixture(db_session)

    report = audit_test_data(db_session)

    assert report.executed is False
    assert {item.label: item.classification for item in report.contents} == {
        "Phase45 Must Read General": "phase45",
    }
    assert {item.label: item.classification for item in report.quiz_questions} == {
        "E2E 通用题目": "e2e",
    }
    assert {item.label: item.classification for item in report.users} == {
        "phase45_admin": "phase45",
    }
    for model, expected in fixture["counts"].items():
        assert len(db_session.scalars(select(model)).all()) == expected


def test_execute_deletes_only_classified_records_and_handles_dependencies(db_session: Session) -> None:
    fixture = _seed_audit_fixture(db_session)

    report = audit_test_data(db_session, execute=True)

    assert report.executed is True
    assert db_session.get(Content, fixture["test_content_id"]) is None
    assert db_session.get(ContentVersion, fixture["test_version_id"]) is None
    assert db_session.get(ContentChunk, fixture["test_chunk_id"]) is None
    assert db_session.get(VectorIndexRecord, fixture["test_vector_id"]) is None
    assert db_session.get(QuizQuestion, fixture["test_quiz_id"]) is None
    assert db_session.get(User, fixture["test_user_id"]) is None

    business_content = db_session.get(Content, fixture["business_content_id"])
    business_quiz = db_session.get(QuizQuestion, fixture["business_quiz_id"])
    dependent_business_quiz = db_session.get(QuizQuestion, fixture["dependent_business_quiz_id"])
    retained_missed_question = db_session.get(MissedQuestion, fixture["test_user_missed_question_id"])

    assert business_content is not None
    assert business_content.title == "客户正式业务话术"
    assert business_quiz is not None
    assert dependent_business_quiz is not None
    assert dependent_business_quiz.related_content_id is None
    assert retained_missed_question is not None
    assert retained_missed_question.user_id is None
    assert db_session.get(User, fixture["business_user_id"]) is not None


def test_phase8_seed_upserts_stable_general_and_full_questions(db_session: Session) -> None:
    seed = _load_phase8_seed()
    owner = _add_user(db_session, username="seed-owner")
    general_content = _add_draft_content(
        db_session,
        creator=owner,
        title="阶段8手测：风险提示标准话术",
        permission_level=ContentLevel.GENERAL.value,
    )
    full_content = _add_draft_content(
        db_session,
        creator=owner,
        title="阶段8手测：全量权限专属话术",
        permission_level=ContentLevel.FULL.value,
    )

    seed.ensure_quiz_questions(
        db=db_session,
        general_related_content_id=general_content.id,
        full_related_content_id=full_content.id,
    )
    db_session.flush()
    first_ids = {
        item.question: item.id
        for item in db_session.scalars(
            select(QuizQuestion).where(QuizQuestion.question.like("阶段8手测题%"))
        ).all()
    }

    seeded_question = db_session.get(QuizQuestion, next(iter(first_ids.values())))
    assert seeded_question is not None
    seeded_question.answer = "错误旧答案"
    seed.ensure_quiz_questions(
        db=db_session,
        general_related_content_id=general_content.id,
        full_related_content_id=full_content.id,
    )
    db_session.flush()

    questions = db_session.scalars(
        select(QuizQuestion)
        .where(QuizQuestion.question.like("阶段8手测题%"))
        .order_by(QuizQuestion.question.asc())
    ).all()
    assert len(questions) == 5
    assert {item.question: item.id for item in questions} == first_ids
    assert [item.permission_level for item in questions].count(ContentLevel.GENERAL.value) == 4
    assert [item.permission_level for item in questions].count(ContentLevel.FULL.value) == 1
    assert all(item.answer != "错误旧答案" for item in questions)
    assert any("循环寿命" in item.question for item in questions)


def test_phase8_seed_updates_drafts_and_publishes_only_changed_snapshots(
    db_session: Session,
) -> None:
    seed = _load_phase8_seed()
    admin = _add_user(db_session, username="phase8_manual_admin")

    first = seed.publish_sample_content(db=db_session, admin=admin)
    first_version_ids = {
        title: content.current_version_id
        for title, content in first.items()
    }
    first_version_count = len(db_session.scalars(select(ContentVersion)).all())

    second = seed.publish_sample_content(db=db_session, admin=admin)
    assert {
        title: content.current_version_id
        for title, content in second.items()
    } == first_version_ids
    assert len(db_session.scalars(select(ContentVersion)).all()) == first_version_count

    title = "阶段8手测：基础开场白"
    expected_payload = {item.title: item for item in seed.sample_contents()}[title]
    target = second[title]
    target.draft_body = "旧草稿正文"
    db_session.commit()

    draft_repaired = seed.publish_sample_content(db=db_session, admin=admin)[title]
    assert draft_repaired.draft_body == expected_payload.body
    assert draft_repaired.current_version_id == first_version_ids[title]
    assert len(db_session.scalars(select(ContentVersion)).all()) == first_version_count

    assert draft_repaired.current_version is not None
    draft_repaired.current_version.body = "旧发布正文"
    draft_repaired.draft_body = "旧发布正文"
    db_session.commit()

    republished = seed.publish_sample_content(db=db_session, admin=admin)[title]
    assert republished.current_version is not None
    assert republished.current_version.body == expected_payload.body
    assert republished.current_version_id != first_version_ids[title]
    assert len(db_session.scalars(select(ContentVersion)).all()) == first_version_count + 1


def test_phase8_seed_source_is_utf8_and_keeps_chinese_literals() -> None:
    source = _phase8_seed_path().read_text(encoding="utf-8")

    assert "阶段8手测：基础开场白" in source
    assert "电池循环寿命" in source
    assert "phase8_manual_general" in source
    assert "\ufffd" not in source


def _seed_audit_fixture(db: Session) -> dict[str, object]:
    test_user = User(
        username="phase45_admin",
        password_hash="test-only",
        display_name="Phase45 Admin",
        account_type=AccountType.ADMIN.value,
        content_level=ContentLevel.FULL.value,
        is_active=True,
    )
    business_user = User(
        username="business_owner",
        password_hash="test-only",
        display_name="Business Owner",
        account_type=AccountType.ADMIN.value,
        content_level=ContentLevel.FULL.value,
        is_active=True,
    )
    db.add_all([test_user, business_user])
    db.flush()

    test_graph = _add_content_graph(
        db,
        creator=test_user,
        title="Phase45 Must Read General",
        hash_prefix="test",
    )
    business_graph = _add_content_graph(
        db,
        creator=business_user,
        title="客户正式业务话术",
        hash_prefix="business",
    )

    test_quiz = QuizQuestion(
        question="E2E 通用题目",
        options=["A", "B"],
        answer="A",
        explanation="测试解析",
        related_content_id=test_graph["content"].id,
        permission_level=ContentLevel.GENERAL.value,
        status=QuestionStatus.ENABLED.value,
    )
    business_quiz = QuizQuestion(
        question="客户正式业务题目",
        options=["A", "B"],
        answer="A",
        explanation="业务解析",
        related_content_id=business_graph["content"].id,
        permission_level=ContentLevel.GENERAL.value,
        status=QuestionStatus.ENABLED.value,
    )
    dependent_business_quiz = QuizQuestion(
        question="业务复习题",
        options=["A", "B"],
        answer="A",
        explanation="保留题目，只解除已删除测试内容的关联",
        related_content_id=test_graph["content"].id,
        permission_level=ContentLevel.GENERAL.value,
        status=QuestionStatus.ENABLED.value,
    )
    test_user_missed_question = MissedQuestion(
        question="保留这条未命中历史",
        user_id=test_user.id,
        account_type=AccountType.ADMIN.value,
        content_level=ContentLevel.FULL.value,
        status=MissedQuestionStatus.NEW.value,
    )
    db.add_all(
        [
            test_quiz,
            business_quiz,
            dependent_business_quiz,
            test_user_missed_question,
        ]
    )
    db.commit()

    models = (
        User,
        Content,
        ContentVersion,
        ContentChunk,
        VectorIndexRecord,
        QuizQuestion,
        MissedQuestion,
    )
    return {
        "test_user_id": test_user.id,
        "business_user_id": business_user.id,
        "test_content_id": test_graph["content"].id,
        "test_version_id": test_graph["version"].id,
        "test_chunk_id": test_graph["chunk"].id,
        "test_vector_id": test_graph["vector"].id,
        "business_content_id": business_graph["content"].id,
        "test_quiz_id": test_quiz.id,
        "business_quiz_id": business_quiz.id,
        "dependent_business_quiz_id": dependent_business_quiz.id,
        "test_user_missed_question_id": test_user_missed_question.id,
        "counts": {model: len(db.scalars(select(model)).all()) for model in models},
    }


def _add_content_graph(
    db: Session,
    *,
    creator: User,
    title: str,
    hash_prefix: str,
) -> dict[str, object]:
    content = Content(
        content_type=ContentType.MUST_READ.value,
        title=title,
        category="测试分类",
        permission_level=ContentLevel.GENERAL.value,
        status=ContentStatus.PUBLISHED.value,
        draft_summary="摘要",
        draft_body="正文",
        draft_payload={"update_body": "正文", "adjustment_points": ["要点"]},
        created_by=creator.id,
    )
    db.add(content)
    db.flush()

    version_kwargs = {
        "content_id": content.id,
        "version_no": 1,
        "title": title,
        "summary": "摘要",
        "body": "正文",
        "structured_payload": {"update_body": "正文", "adjustment_points": ["要点"]},
        "created_by": creator.id,
    }
    if hasattr(ContentVersion, "permission_level"):
        version_kwargs["permission_level"] = ContentLevel.GENERAL.value
    version = ContentVersion(**version_kwargs)
    db.add(version)
    db.flush()
    content.current_version_id = version.id

    chunk = ContentChunk(
        content_id=content.id,
        version_id=version.id,
        chunk_type=ContentType.MUST_READ.value,
        chunk_text="测试 chunk",
        sort_order=0,
        content_hash=f"{hash_prefix}-chunk",
        permission_level=ContentLevel.GENERAL.value,
        is_active=True,
    )
    db.add(chunk)
    db.flush()
    vector = VectorIndexRecord(
        content_id=content.id,
        version_id=version.id,
        chunk_id=chunk.id,
        milvus_collection="test_collection",
        milvus_primary_key=f"{hash_prefix}-vector",
        embedding_model="test-embedding",
        embedding_dimension=3,
        content_hash=f"{hash_prefix}-chunk",
        is_active=True,
    )
    db.add(vector)
    db.flush()
    return {"content": content, "version": version, "chunk": chunk, "vector": vector}


def _add_user(db: Session, *, username: str) -> User:
    user = User(
        username=username,
        password_hash="test-only",
        display_name=username,
        account_type=AccountType.ADMIN.value,
        content_level=ContentLevel.FULL.value,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _add_draft_content(
    db: Session,
    *,
    creator: User,
    title: str,
    permission_level: str,
) -> Content:
    content = Content(
        content_type=ContentType.STANDARD_SCRIPT.value,
        title=title,
        category="种子测试",
        permission_level=permission_level,
        status=ContentStatus.DRAFT.value,
        draft_summary="摘要",
        draft_body="正文",
        draft_payload={"scene": "场景"},
        created_by=creator.id,
    )
    db.add(content)
    db.flush()
    return content


def _phase8_seed_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "seed-phase8-manual-data.py"


def _load_phase8_seed() -> ModuleType:
    path = _phase8_seed_path()
    spec = importlib.util.spec_from_file_location("phase8_manual_seed", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load seed module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
