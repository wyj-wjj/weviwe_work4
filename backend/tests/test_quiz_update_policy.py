from alembic import command
from sqlalchemy import create_engine, inspect, select

from app.models.content import Content, ContentVersion
from app.models.quiz import QuizQuestion
from test_migrations_phase2 import make_alembic_config


def base_content_payload(**overrides):
    payload = {
        "content_type": "base_script",
        "title": "Storage safety script",
        "category": "safety",
        "permission_level": "general",
        "summary": "Initial safety summary",
        "body": "Confirm the customer scenario before giving safety commitments.",
        "structured_payload": {"points": ["confirm scenario", "avoid over-commitment"]},
    }
    payload.update(overrides)
    return payload


def quiz_payload(index: int, **overrides):
    payload = {
        "question": f"What should employee do first in scenario {index}?",
        "options": ["Confirm scenario", "Quote immediately"],
        "answer": "Confirm scenario",
        "explanation": "The employee must confirm the scenario before answering.",
        "related_content_id": None,
        "related_version_id": None,
        "permission_level": "general",
        "status": "enabled",
        "source_type": "manual",
        "review_status": "approved",
        "needs_review": False,
        "review_reason": None,
    }
    payload.update(overrides)
    return payload


def create_and_publish_content(
    client,
    admin_headers,
    *,
    payload=None,
    publish_payload=None,
) -> tuple[int, int]:
    created = client.post(
        "/api/admin/contents",
        json=payload or base_content_payload(),
        headers=admin_headers,
    )
    assert created.status_code == 201
    content_id = created.json()["id"]
    published = client.post(
        f"/api/admin/contents/{content_id}/publish",
        json=publish_payload or {"update_level": "major", "change_summary": "Initial release"},
        headers=admin_headers,
    )
    assert published.status_code == 200
    return content_id, published.json()["current_version_id"]


def test_quiz_update_policy_migration_adds_version_and_review_columns(sqlite_url: str) -> None:
    command.upgrade(make_alembic_config(sqlite_url), "head")

    engine = create_engine(sqlite_url)
    inspector = inspect(engine)
    version_columns = {column["name"]: column for column in inspector.get_columns("content_versions")}
    quiz_columns = {column["name"]: column for column in inspector.get_columns("quiz_questions")}

    assert {
        "update_level",
        "change_summary",
        "quiz_action",
        "ai_suggested_update_level",
        "ai_suggestion_reason",
    } <= set(version_columns)
    assert version_columns["update_level"]["nullable"] is False
    assert version_columns["quiz_action"]["nullable"] is False

    assert {
        "related_version_id",
        "source_type",
        "review_status",
        "needs_review",
        "review_reason",
    } <= set(quiz_columns)
    assert quiz_columns["source_type"]["nullable"] is False
    assert quiz_columns["review_status"]["nullable"] is False
    assert quiz_columns["needs_review"]["nullable"] is False
    engine.dispose()


def test_publishing_medium_update_marks_related_questions_for_review(
    client,
    admin_headers,
    general_user_headers,
    db_session,
):
    content_id, version_id = create_and_publish_content(client, admin_headers)
    created_question = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(1, related_content_id=content_id, related_version_id=version_id),
        headers=admin_headers,
    )
    assert created_question.status_code == 201
    question_id = created_question.json()["id"]
    assert created_question.json()["related_version_id"] == version_id
    assert created_question.json()["source_type"] == "manual"
    assert created_question.json()["review_status"] == "approved"
    assert created_question.json()["needs_review"] is False

    updated = client.patch(
        f"/api/admin/contents/{content_id}",
        json={
            "body": "A local safety rule changed and related quiz questions need review.",
            "summary": "Local rule changed",
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200

    republished = client.post(
        f"/api/admin/contents/{content_id}/publish",
        json={"update_level": "medium", "change_summary": "Local rule changed"},
        headers=admin_headers,
    )
    assert republished.status_code == 200

    versions = list(
        db_session.scalars(
            select(ContentVersion)
            .where(ContentVersion.content_id == content_id)
            .order_by(ContentVersion.version_no)
        )
    )
    assert [version.version_no for version in versions] == [1, 2]
    assert versions[1].update_level == "medium"
    assert versions[1].change_summary == "Local rule changed"
    assert versions[1].quiz_action == "review_related"

    db_session.expire_all()
    question = db_session.get(QuizQuestion, question_id)
    assert question.needs_review is True
    assert question.status == "disabled"
    assert "v2" in question.review_reason
    assert "旧版本" in question.review_reason

    employee_quiz = client.get("/api/app/quiz", headers=general_user_headers)
    assert employee_quiz.status_code == 200
    assert question_id not in {item["id"] for item in employee_quiz.json()["items"]}


def test_employee_quiz_only_uses_approved_non_review_questions_with_visible_sources(
    client,
    admin_headers,
    general_user_headers,
):
    valid_id, valid_version_id = create_and_publish_content(
        client,
        admin_headers,
        payload=base_content_payload(title="Visible general source"),
    )
    offline_id, offline_version_id = create_and_publish_content(
        client,
        admin_headers,
        payload=base_content_payload(title="Offline source"),
    )
    client.post(f"/api/admin/contents/{offline_id}/offline", headers=admin_headers)
    full_id, full_version_id = create_and_publish_content(
        client,
        admin_headers,
        payload=base_content_payload(
            title="Full-only source",
            permission_level="full",
        ),
    )

    visible = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(1, related_content_id=valid_id, related_version_id=valid_version_id),
        headers=admin_headers,
    ).json()["id"]
    pending_review = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(2, review_status="pending_review"),
        headers=admin_headers,
    ).json()["id"]
    needs_review = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(3, needs_review=True, review_reason="content changed"),
        headers=admin_headers,
    ).json()["id"]
    offline_related = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(4, related_content_id=offline_id, related_version_id=offline_version_id),
        headers=admin_headers,
    ).json()["id"]
    full_related = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(5, related_content_id=full_id, related_version_id=full_version_id),
        headers=admin_headers,
    ).json()["id"]

    response = client.get("/api/app/quiz", headers=general_user_headers)
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}

    assert visible in ids
    assert pending_review not in ids
    assert needs_review not in ids
    assert offline_related not in ids
    assert full_related not in ids
