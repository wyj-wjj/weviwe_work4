from sqlalchemy import inspect

from app.models.quiz import QuizQuestion


def quiz_payload(index: int, *, permission_level: str = "general", status: str = "enabled"):
    return {
        "question": f"第 {index} 题应该如何处理？",
        "options": ["确认需求", "直接报价", "结束沟通"],
        "answer": "确认需求",
        "explanation": "先确认需求，再进入推荐。",
        "permission_level": permission_level,
        "status": status,
    }


def create_quiz_questions(client, admin_headers, count: int, *, permission_level: str = "general"):
    ids = []
    for index in range(count):
        response = client.post(
            "/api/admin/quiz-questions",
            json=quiz_payload(index, permission_level=permission_level),
            headers=admin_headers,
        )
        assert response.status_code == 201
        ids.append(response.json()["id"])
    return ids


def test_admin_can_create_edit_enable_disable_and_list_quiz_questions(client, admin_headers):
    created = client.post("/api/admin/quiz-questions", json=quiz_payload(1), headers=admin_headers)
    assert created.status_code == 201
    question_id = created.json()["id"]

    edited = client.patch(
        f"/api/admin/quiz-questions/{question_id}",
        json={"question": "更新后的题干？", "status": "disabled"},
        headers=admin_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["question"] == "更新后的题干？"
    assert edited.json()["status"] == "disabled"

    enabled = client.post(f"/api/admin/quiz-questions/{question_id}/enable", headers=admin_headers)
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "enabled"

    disabled = client.post(f"/api/admin/quiz-questions/{question_id}/disable", headers=admin_headers)
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    listing = client.get("/api/admin/quiz-questions", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


def test_employee_quiz_returns_five_to_ten_visible_enabled_questions(
    client,
    admin_headers,
    general_user_headers,
    full_user_headers,
):
    create_quiz_questions(client, admin_headers, 6, permission_level="general")
    create_quiz_questions(client, admin_headers, 6, permission_level="full")
    client.post("/api/admin/quiz-questions", json=quiz_payload(99, status="disabled"), headers=admin_headers)

    general = client.get("/api/app/quiz", headers=general_user_headers)
    assert general.status_code == 200
    general_items = general.json()["items"]
    assert 5 <= len(general_items) <= 10
    assert {item["permission_level"] for item in general_items} == {"general"}
    assert all("answer" not in item for item in general_items)

    full = client.get("/api/app/quiz", headers=full_user_headers)
    assert full.status_code == 200
    full_items = full.json()["items"]
    assert 5 <= len(full_items) <= 10
    assert {item["permission_level"] for item in full_items} == {"general", "full"}


def test_quiz_submit_returns_explanations_without_persisting_attempts(client, admin_headers, general_user_headers, db_session):
    question_ids = create_quiz_questions(client, admin_headers, 5, permission_level="general")

    response = client.post(
        "/api/app/quiz/submit",
        json={"answers": [{"question_id": question_ids[0], "selected_answer": "直接报价"}]},
        headers=general_user_headers,
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["question_id"] == question_ids[0]
    assert result["is_correct"] is False
    assert result["correct_answer"] == "确认需求"
    assert result["explanation"]

    assert db_session.query(QuizQuestion).count() == 5
    assert "score" not in response.json()
    table_names = set(inspect(db_session.bind).get_table_names())
    assert "quiz_attempts" not in table_names
    assert "quiz_scores" not in table_names


def test_quiz_submit_rejects_questions_outside_current_user_permission(client, admin_headers, general_user_headers):
    question_ids = create_quiz_questions(client, admin_headers, 5, permission_level="full")

    response = client.post(
        "/api/app/quiz/submit",
        json={"answers": [{"question_id": question_ids[0], "selected_answer": "anything"}]},
        headers=general_user_headers,
    )

    assert response.status_code == 404
