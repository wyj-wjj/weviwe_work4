import json
from types import SimpleNamespace

from alembic import command
from sqlalchemy import create_engine, inspect

from app.api.deps import get_dashscope_client
from app.integrations.dashscope import ChatGeneration, EmbeddingResult
from app.main import app
from test_migrations_phase2 import make_alembic_config


def content_payload(**overrides):
    payload = {
        "content_type": "must_read",
        "title": "消防验收新要求",
        "category": "消防",
        "permission_level": "general",
        "summary": "消防验收口径调整",
        "body": "消防验收必须先确认配置清单、验收口径和客户承诺边界。",
        "structured_payload": {
            "update_body": "消防验收必须先确认配置清单、验收口径和客户承诺边界。",
            "adjustment_points": ["确认配置清单", "不得越权承诺"],
        },
    }
    payload.update(overrides)
    return payload


def quiz_payload(index: int, **overrides):
    payload = {
        "question": f"普通题 {index} 应该怎么处理？",
        "options": ["先确认信息", "直接承诺"],
        "answer": "先确认信息",
        "explanation": "普通题解析。",
        "related_content_id": None,
        "related_version_id": None,
        "permission_level": "general",
        "status": "enabled",
        "source_type": "manual",
        "review_status": "approved",
        "needs_review": False,
        "review_reason": None,
        "priority": 0,
    }
    payload.update(overrides)
    return payload


class QuizJsonDashScopeClient:
    def __init__(self, answer_payload: dict):
        self.answer_payload = answer_payload
        self.embedding_requests: list[str] = []
        self.chat_requests: list[dict] = []

    def embed_text(self, text: str) -> EmbeddingResult:
        self.embedding_requests.append(text)
        return EmbeddingResult(vector=[0.1, 0.2, 0.3], model="fake-embedding")

    def generate_answer(
        self,
        *,
        question: str,
        contexts: list[dict],
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatGeneration:
        self.chat_requests.append(
            {
                "question": question,
                "contexts": contexts,
                "model_name": model_name,
                "timeout_seconds": timeout_seconds,
            }
        )
        return ChatGeneration(answer_text=json.dumps(self.answer_payload, ensure_ascii=False), usage={})


def generated_questions_payload():
    return {
        "questions": [
            {
                "question": "消防验收前员工必须先确认什么？",
                "options": ["配置清单和验收口径", "客户预算"],
                "answer": "配置清单和验收口径",
                "explanation": "来源明确要求先确认配置清单、验收口径和承诺边界。",
            },
            {
                "question": "面对客户承诺时应注意什么？",
                "options": ["不得越权承诺", "可以先答应再确认"],
                "answer": "不得越权承诺",
                "explanation": "来源强调客户承诺边界，不能越权承诺。",
            },
        ]
    }


def create_content(client, admin_headers, **overrides) -> int:
    response = client.post("/api/admin/contents", json=content_payload(**overrides), headers=admin_headers)
    assert response.status_code == 201
    return response.json()["id"]


def publish_major(client, admin_headers, content_id: int):
    response = client.post(
        f"/api/admin/contents/{content_id}/publish",
        json={"update_level": "major", "change_summary": "消防验收关键规则变化"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    return response.json()


def generate_quiz_for_version(client, admin_headers, content_id: int, version_id: int):
    response = client.post(
        f"/api/admin/contents/{content_id}/versions/{version_id}/generate-quiz",
        json={"create_quiz_set": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    return response.json()


def test_quiz_phase2_phase3_migration_adds_generation_batch_and_quiz_set_tables(sqlite_url: str) -> None:
    command.upgrade(make_alembic_config(sqlite_url), "head")

    engine = create_engine(sqlite_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    quiz_columns = {column["name"] for column in inspector.get_columns("quiz_questions")}
    batch_columns = {column["name"] for column in inspector.get_columns("quiz_generation_batches")}
    set_columns = {column["name"] for column in inspector.get_columns("quiz_sets")}
    item_columns = {column["name"] for column in inspector.get_columns("quiz_question_set_items")}

    assert {"quiz_generation_batches", "quiz_sets", "quiz_question_set_items"} <= tables
    assert {"generation_batch_id", "expires_at", "priority"} <= quiz_columns
    assert {
        "content_id",
        "version_id",
        "update_level",
        "status",
        "model_name",
        "prompt_version",
        "requested_count",
        "generated_count",
        "created_by",
        "created_at",
        "error_message",
    } <= batch_columns
    assert {
        "title",
        "description",
        "related_content_id",
        "related_version_id",
        "update_level",
        "permission_level",
        "status",
        "expires_at",
        "created_at",
    } <= set_columns
    assert {"quiz_set_id", "question_id", "sort_order"} <= item_columns
    engine.dispose()


def test_major_publish_defers_ai_candidate_generation_to_history_action(
    client,
    admin_headers,
):
    fake = QuizJsonDashScopeClient(generated_questions_payload())
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    content_id = create_content(client, admin_headers)
    published = publish_major(client, admin_headers, content_id)
    version_id = published["current_version_id"]

    assert published["quiz_generation_status"] == "pending"
    assert fake.chat_requests == []

    batches = client.get("/api/admin/quiz-generation-batches", headers=admin_headers)
    assert batches.status_code == 200
    assert batches.json()["total"] == 0

    batch = generate_quiz_for_version(client, admin_headers, content_id, version_id)
    assert batch["content_id"] == content_id
    assert batch["version_id"] == version_id
    assert batch["update_level"] == "major"
    assert batch["status"] == "completed"
    assert batch["requested_count"] == 5
    assert batch["generated_count"] == 2


def test_manual_generation_uses_quiz_model_and_timeout(client, admin_headers):
    fake = QuizJsonDashScopeClient(generated_questions_payload())
    fake.settings = SimpleNamespace(
        dashscope_chat_model="chat-model",
        dashscope_quiz_model="quiz-model",
        dashscope_quiz_timeout_seconds=91.0,
    )
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    content_id = create_content(client, admin_headers)
    published = publish_major(client, admin_headers, content_id)

    batch = generate_quiz_for_version(client, admin_headers, content_id, published["current_version_id"])

    assert batch["model_name"] == "quiz-model"
    assert fake.chat_requests[0]["model_name"] == "quiz-model"
    assert fake.chat_requests[0]["timeout_seconds"] == 91.0


def test_manual_major_generation_creates_disabled_ai_candidates_and_topic_set(
    client,
    admin_headers,
    general_user_headers,
):
    fake = QuizJsonDashScopeClient(generated_questions_payload())
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    content_id = create_content(client, admin_headers)
    published = publish_major(client, admin_headers, content_id)
    version_id = published["current_version_id"]
    generated_batch = generate_quiz_for_version(client, admin_headers, content_id, version_id)

    batches = client.get("/api/admin/quiz-generation-batches", headers=admin_headers)
    assert batches.status_code == 200
    batch = batches.json()["items"][0]
    assert batch["id"] == generated_batch["id"]
    assert batch["content_id"] == content_id
    assert batch["version_id"] == version_id
    assert batch["update_level"] == "major"
    assert batch["status"] == "completed"
    assert batch["requested_count"] == 5
    assert batch["generated_count"] == 2

    questions = client.get("/api/admin/quiz-questions", headers=admin_headers)
    assert questions.status_code == 200
    generated = [
        item for item in questions.json()["items"]
        if item["generation_batch_id"] == batch["id"]
    ]
    assert len(generated) == 2
    assert {item["source_type"] for item in generated} == {"ai_generated"}
    assert {item["review_status"] for item in generated} == {"pending_review"}
    assert {item["status"] for item in generated} == {"disabled"}
    assert {item["related_version_id"] for item in generated} == {version_id}
    assert all(item["priority"] >= 100 for item in generated)

    sets = client.get("/api/admin/quiz-sets", headers=admin_headers)
    assert sets.status_code == 200
    quiz_set = sets.json()["items"][0]
    assert quiz_set["related_content_id"] == content_id
    assert quiz_set["related_version_id"] == version_id
    assert quiz_set["update_level"] == "major"
    assert quiz_set["question_count"] == 2

    employee_quiz = client.get("/api/app/quiz", headers=general_user_headers)
    employee_ids = {item["id"] for item in employee_quiz.json()["items"]}
    assert employee_ids.isdisjoint({item["id"] for item in generated})


def test_admin_can_approve_ai_candidate_and_release_it_to_employee_quiz(
    client,
    admin_headers,
    general_user_headers,
):
    fake = QuizJsonDashScopeClient(generated_questions_payload())
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    content_id = create_content(client, admin_headers)
    published = publish_major(client, admin_headers, content_id)
    generate_quiz_for_version(client, admin_headers, content_id, published["current_version_id"])

    questions = client.get("/api/admin/quiz-questions", headers=admin_headers).json()["items"]
    generated = [item for item in questions if item["generation_batch_id"] is not None]
    approved_id = generated[0]["id"]
    assert generated[0]["review_status"] == "pending_review"
    assert generated[0]["status"] == "disabled"

    approved = client.post(
        f"/api/admin/quiz-questions/{approved_id}/approve",
        headers=admin_headers,
    )

    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"
    assert approved.json()["status"] == "enabled"
    assert approved.json()["needs_review"] is False
    assert approved.json()["review_reason"] is None

    employee_quiz = client.get("/api/app/quiz", headers=general_user_headers)
    assert employee_quiz.status_code == 200
    assert approved_id in {item["id"] for item in employee_quiz.json()["items"]}


def test_admin_can_reject_ai_candidate_and_keep_it_out_of_employee_quiz(
    client,
    admin_headers,
    general_user_headers,
):
    fake = QuizJsonDashScopeClient(generated_questions_payload())
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    content_id = create_content(client, admin_headers)
    published = publish_major(client, admin_headers, content_id)
    generate_quiz_for_version(client, admin_headers, content_id, published["current_version_id"])

    questions = client.get("/api/admin/quiz-questions", headers=admin_headers).json()["items"]
    rejected_id = next(item["id"] for item in questions if item["generation_batch_id"] is not None)

    rejected = client.post(
        f"/api/admin/quiz-questions/{rejected_id}/reject",
        headers=admin_headers,
    )

    assert rejected.status_code == 200
    assert rejected.json()["review_status"] == "rejected"
    assert rejected.json()["status"] == "disabled"
    assert rejected.json()["needs_review"] is False

    employee_quiz = client.get("/api/app/quiz", headers=general_user_headers)
    assert employee_quiz.status_code == 200
    assert rejected_id not in {item["id"] for item in employee_quiz.json()["items"]}


def test_offline_content_deactivates_related_topic_set_and_blocks_approved_questions(
    client,
    admin_headers,
    general_user_headers,
):
    fake = QuizJsonDashScopeClient(generated_questions_payload())
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    content_id = create_content(client, admin_headers)
    published = publish_major(client, admin_headers, content_id)
    generate_quiz_for_version(client, admin_headers, content_id, published["current_version_id"])

    questions = client.get("/api/admin/quiz-questions", headers=admin_headers).json()["items"]
    generated_ids = [
        item["id"] for item in questions
        if item["generation_batch_id"] is not None
    ]
    for question_id in generated_ids:
        approved = client.patch(
            f"/api/admin/quiz-questions/{question_id}",
            json={"review_status": "approved", "status": "enabled"},
            headers=admin_headers,
        )
        assert approved.status_code == 200

    before_offline = client.get("/api/app/quiz", headers=general_user_headers)
    assert set(generated_ids).issubset({item["id"] for item in before_offline.json()["items"]})

    offline = client.post(f"/api/admin/contents/{content_id}/offline", headers=admin_headers)
    assert offline.status_code == 200

    sets = client.get("/api/admin/quiz-sets", headers=admin_headers)
    assert sets.status_code == 200
    assert sets.json()["items"][0]["status"] == "inactive"

    after_offline = client.get("/api/app/quiz", headers=general_user_headers)
    assert {item["id"] for item in after_offline.json()["items"]}.isdisjoint(generated_ids)


def test_offline_content_auto_rejects_pending_ai_candidates_and_blocks_release_actions(
    client,
    admin_headers,
):
    fake = QuizJsonDashScopeClient(generated_questions_payload())
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    content_id = create_content(client, admin_headers)
    published = publish_major(client, admin_headers, content_id)
    generate_quiz_for_version(client, admin_headers, content_id, published["current_version_id"])

    before_offline = client.get("/api/admin/quiz-questions", headers=admin_headers)
    assert before_offline.status_code == 200
    generated_ids = [
        item["id"]
        for item in before_offline.json()["items"]
        if item["generation_batch_id"] is not None
    ]
    assert generated_ids

    offline = client.post(f"/api/admin/contents/{content_id}/offline", headers=admin_headers)
    assert offline.status_code == 200

    after_offline = client.get("/api/admin/quiz-questions", headers=admin_headers)
    assert after_offline.status_code == 200
    generated = [
        item
        for item in after_offline.json()["items"]
        if item["id"] in generated_ids
    ]
    assert {item["review_status"] for item in generated} == {"rejected"}
    assert {item["status"] for item in generated} == {"disabled"}
    assert {item["source_valid"] for item in generated} == {False}
    assert {item["source_invalid_reason"] for item in generated} == {"source_content_offline"}
    assert all("下线" in (item["review_reason"] or "") for item in generated)

    for question_id in generated_ids:
        approved = client.post(
            f"/api/admin/quiz-questions/{question_id}/approve",
            headers=admin_headers,
        )
        assert approved.status_code == 409
        assert approved.json()["error"]["code"] == "quiz_source_invalid"

        enabled = client.post(
            f"/api/admin/quiz-questions/{question_id}/enable",
            headers=admin_headers,
        )
        assert enabled.status_code == 409
        assert enabled.json()["error"]["code"] == "quiz_source_invalid"


def test_republish_invalidates_old_version_candidates_and_deactivates_old_topic_set(
    client,
    admin_headers,
):
    fake = QuizJsonDashScopeClient(generated_questions_payload())
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    content_id = create_content(client, admin_headers)
    first = publish_major(client, admin_headers, content_id)
    first_version_id = first["current_version_id"]
    generate_quiz_for_version(client, admin_headers, content_id, first_version_id)

    questions = client.get("/api/admin/quiz-questions", headers=admin_headers).json()["items"]
    generated_ids = [
        item["id"]
        for item in questions
        if item["generation_batch_id"] is not None
    ]
    assert generated_ids

    updated = client.patch(
        f"/api/admin/contents/{content_id}",
        json={"body": "修正后的消防验收规则，必须重新按新版审核题目。"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    second = client.post(
        f"/api/admin/contents/{content_id}/publish",
        json={"update_level": "major", "change_summary": "修正错误大更新"},
        headers=admin_headers,
    )
    assert second.status_code == 200
    assert second.json()["current_version_id"] != first_version_id

    sets = client.get("/api/admin/quiz-sets", headers=admin_headers)
    assert sets.status_code == 200
    first_set = next(
        item for item in sets.json()["items"]
        if item["related_version_id"] == first_version_id
    )
    assert first_set["status"] == "inactive"

    after_republish = client.get("/api/admin/quiz-questions", headers=admin_headers)
    assert after_republish.status_code == 200
    stale_generated = [
        item
        for item in after_republish.json()["items"]
        if item["id"] in generated_ids
    ]
    assert {item["review_status"] for item in stale_generated} == {"rejected"}
    assert {item["status"] for item in stale_generated} == {"disabled"}
    assert {item["source_valid"] for item in stale_generated} == {False}
    assert {item["source_invalid_reason"] for item in stale_generated} == {"source_version_stale"}
    assert all("旧版本" in (item["review_reason"] or "") for item in stale_generated)

    blocked = client.post(
        f"/api/admin/quiz-questions/{generated_ids[0]}/approve",
        headers=admin_headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "quiz_source_invalid"


def test_employee_quiz_filters_questions_bound_to_stale_content_versions(
    client,
    admin_headers,
    general_user_headers,
):
    content_id = create_content(client, admin_headers)
    first = publish_major(client, admin_headers, content_id)
    first_version_id = first["current_version_id"]

    updated = client.patch(
        f"/api/admin/contents/{content_id}",
        json={"body": "新版内容已经替换旧版本。"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    second = client.post(
        f"/api/admin/contents/{content_id}/publish",
        json={"update_level": "major", "change_summary": "发布新版内容"},
        headers=admin_headers,
    )
    assert second.status_code == 200
    second_version_id = second.json()["current_version_id"]
    assert second_version_id != first_version_id

    stale = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(
            77,
            related_content_id=content_id,
            related_version_id=first_version_id,
            review_status="approved",
            status="enabled",
        ),
        headers=admin_headers,
    )
    assert stale.status_code == 201
    current = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(
            78,
            related_content_id=content_id,
            related_version_id=second_version_id,
            review_status="approved",
            status="enabled",
        ),
        headers=admin_headers,
    )
    assert current.status_code == 201

    employee_quiz = client.get("/api/app/quiz", headers=general_user_headers)
    assert employee_quiz.status_code == 200
    returned_ids = {item["id"] for item in employee_quiz.json()["items"]}
    assert stale.json()["id"] not in returned_ids
    assert current.json()["id"] in returned_ids

    submit_stale = client.post(
        "/api/app/quiz/submit",
        json={"answers": [{"question_id": stale.json()["id"], "selected_answer": "先确认信息"}]},
        headers=general_user_headers,
    )
    assert submit_stale.status_code == 404


def test_approved_major_topic_questions_are_prioritized_for_employee_quiz(
    client,
    admin_headers,
    general_user_headers,
):
    fake = QuizJsonDashScopeClient(generated_questions_payload())
    app.dependency_overrides[get_dashscope_client] = lambda: fake

    normal_ids = []
    for index in range(10):
        response = client.post(
            "/api/admin/quiz-questions",
            json=quiz_payload(index),
            headers=admin_headers,
        )
        assert response.status_code == 201
        normal_ids.append(response.json()["id"])

    content_id = create_content(client, admin_headers)
    published = publish_major(client, admin_headers, content_id)
    generate_quiz_for_version(client, admin_headers, content_id, published["current_version_id"])

    questions = client.get("/api/admin/quiz-questions", headers=admin_headers).json()["items"]
    generated_ids = [
        item["id"] for item in questions
        if item["generation_batch_id"] is not None
    ]
    assert len(generated_ids) == 2

    for question_id in generated_ids:
        approved = client.patch(
            f"/api/admin/quiz-questions/{question_id}",
            json={"review_status": "approved", "status": "enabled"},
            headers=admin_headers,
        )
        assert approved.status_code == 200

    employee_quiz = client.get("/api/app/quiz", headers=general_user_headers)
    assert employee_quiz.status_code == 200
    returned_ids = [item["id"] for item in employee_quiz.json()["items"]]

    assert returned_ids[:2] == generated_ids
    assert set(generated_ids).issubset(returned_ids)
    assert len(set(normal_ids).intersection(returned_ids)) == 8
