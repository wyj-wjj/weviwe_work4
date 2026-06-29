from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, inspect

from app.models.quiz import QuizQuestion
from app.models.content import Content
from test_admin_content_phase4 import base_payload, must_read_payload, standard_payload


def quiz_payload(
    index: int,
    *,
    permission_level: str = "general",
    status: str = "enabled",
    related_content_id: int | None = None,
    priority: int = 0,
):
    return {
        "question": f"第 {index} 题应该如何处理？",
        "options": ["确认需求", "直接报价", "结束沟通"],
        "answer": "确认需求",
        "explanation": "先确认需求，再进入推荐。",
        "related_content_id": related_content_id,
        "permission_level": permission_level,
        "status": status,
        "priority": priority,
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


def create_published_content(client, admin_headers, payload):
    created = client.post("/api/admin/contents", json=payload, headers=admin_headers)
    assert created.status_code == 201
    content_id = created.json()["id"]
    published = client.post(f"/api/admin/contents/{content_id}/publish", headers=admin_headers)
    assert published.status_code == 200
    return content_id


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


def test_admin_quiz_pagination_preloads_distinct_related_contents_with_bounded_queries(
    client,
    admin_headers,
    db_session,
):
    for index in range(5):
        content = client.post(
            "/api/admin/contents",
            json=base_payload(title=f"后台关联话术 {index}"),
            headers=admin_headers,
        )
        assert content.status_code == 201
        question = client.post(
            "/api/admin/quiz-questions",
            json=quiz_payload(index, related_content_id=content.json()["id"]),
            headers=admin_headers,
        )
        assert question.status_code == 201

    db_session.expunge_all()
    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record_statement)
    try:
        response = client.get(
            "/api/admin/quiz-questions?page=1&page_size=5",
            headers=admin_headers,
        )
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 5
    content_selects = [
        " ".join(statement.split())
        for statement in statements
        if "FROM contents" in statement
    ]
    assert len(content_selects) <= 1


def test_employee_quiz_returns_five_to_ten_visible_enabled_questions(
    client,
    admin_headers,
    general_user_headers,
    full_user_headers,
):
    general_ids = create_quiz_questions(client, admin_headers, 12, permission_level="general")
    full_ids = create_quiz_questions(client, admin_headers, 1, permission_level="full")
    client.post("/api/admin/quiz-questions", json=quiz_payload(99, status="disabled"), headers=admin_headers)

    general = client.get("/api/app/quiz", headers=general_user_headers)
    assert general.status_code == 200
    general_items = general.json()["items"]
    assert len(general_items) == 10
    assert [item["id"] for item in general_items] == general_ids[:10]
    assert {item["permission_level"] for item in general_items} == {"general"}
    assert all("answer" not in item for item in general_items)

    full = client.get("/api/app/quiz", headers=full_user_headers)
    assert full.status_code == 200
    full_items = full.json()["items"]
    assert len(full_items) == 10
    assert {item["permission_level"] for item in full_items} == {"general", "full"}
    assert [item["id"] for item in full_items] == full_ids + general_ids[:9]

    repeated = client.get("/api/app/quiz", headers=full_user_headers)
    assert [item["id"] for item in repeated.json()["items"]] == [item["id"] for item in full_items]


def test_general_quiz_query_limits_rows_in_sql(
    client,
    admin_headers,
    general_user_headers,
    db_session,
):
    create_quiz_questions(client, admin_headers, 20, permission_level="general")
    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record_statement)
    try:
        response = client.get("/api/app/quiz", headers=general_user_headers)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    quiz_selects = [
        " ".join(statement.split())
        for statement in statements
        if "FROM quiz_questions" in statement
    ]
    assert len(quiz_selects) == 1
    assert "LIMIT" in quiz_selects[0].upper()


def test_full_quiz_uses_full_questions_when_no_general_questions_exist(
    client,
    admin_headers,
    full_user_headers,
):
    full_ids = create_quiz_questions(client, admin_headers, 12, permission_level="full")

    response = client.get("/api/app/quiz", headers=full_user_headers)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == full_ids[:10]


def test_full_quiz_returns_all_available_questions_when_total_is_below_ten(
    client,
    admin_headers,
    full_user_headers,
):
    general_ids = create_quiz_questions(client, admin_headers, 2, permission_level="general")
    full_ids = create_quiz_questions(client, admin_headers, 3, permission_level="full")

    response = client.get("/api/app/quiz", headers=full_user_headers)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        full_ids[0],
        *general_ids,
        *full_ids[1:],
    ]


def test_employee_quiz_latest_prioritizes_recent_related_updates_and_review_filters_old_categories(
    client,
    admin_headers,
    general_user_headers,
    db_session,
):
    old_content_id = create_published_content(
        client,
        admin_headers,
        base_payload(title="旧价格话术", category="价格口径", permission_level="general"),
    )
    new_content_id = create_published_content(
        client,
        admin_headers,
        base_payload(title="最新风控话术", category="风控口径", permission_level="general"),
    )
    now = datetime(2026, 6, 29, 10, 0, tzinfo=UTC)
    old_content = db_session.get(Content, old_content_id)
    new_content = db_session.get(Content, new_content_id)
    old_content.current_version.published_at = now - timedelta(days=30)
    new_content.current_version.published_at = now
    db_session.commit()

    old_question = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(1, related_content_id=old_content_id, priority=20),
        headers=admin_headers,
    )
    assert old_question.status_code == 201
    new_question = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(2, related_content_id=new_content_id, priority=20),
        headers=admin_headers,
    )
    assert new_question.status_code == 201
    standalone_question = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(3, priority=0),
        headers=admin_headers,
    )
    assert standalone_question.status_code == 201

    latest = client.get("/api/app/quiz?mode=latest", headers=general_user_headers)

    assert latest.status_code == 200
    assert [item["id"] for item in latest.json()["items"][:2]] == [
        new_question.json()["id"],
        old_question.json()["id"],
    ]

    review = client.get(
        "/api/app/quiz?mode=review&category=价格口径",
        headers=general_user_headers,
    )

    assert review.status_code == 200
    assert [item["id"] for item in review.json()["items"]] == [old_question.json()["id"]]


def test_employee_quiz_preloads_distinct_related_contents_with_bounded_queries(
    client,
    admin_headers,
    general_user_headers,
    db_session,
):
    for index in range(10):
        content_id = create_published_content(
            client,
            admin_headers,
            base_payload(title=f"关联话术 {index}", permission_level="general"),
        )
        created = client.post(
            "/api/admin/quiz-questions",
            json=quiz_payload(index, related_content_id=content_id),
            headers=admin_headers,
        )
        assert created.status_code == 201

    db_session.expunge_all()
    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record_statement)
    try:
        response = client.get("/api/app/quiz", headers=general_user_headers)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    content_selects = [
        " ".join(statement.split())
        for statement in statements
        if "FROM contents" in statement
    ]
    assert len(content_selects) <= 1


def test_employee_quiz_projects_only_visible_published_related_content(
    client,
    admin_headers,
    general_user_headers,
):
    base_id = create_published_content(
        client,
        admin_headers,
        base_payload(title="可见基础话术", permission_level="general"),
    )
    standard_id = create_published_content(
        client,
        admin_headers,
        standard_payload(title="可见标准话术", permission_level="general"),
    )
    must_read_id = create_published_content(
        client,
        admin_headers,
        must_read_payload(title="可见最新必读", permission_level="general"),
    )
    offline_id = create_published_content(
        client,
        admin_headers,
        base_payload(title="已下线关联内容", permission_level="general"),
    )
    offline = client.post(f"/api/admin/contents/{offline_id}/offline", headers=admin_headers)
    assert offline.status_code == 200
    full_id = create_published_content(
        client,
        admin_headers,
        standard_payload(title="无权关联内容", permission_level="full"),
    )

    relation_cases = [
        (base_id, "base_script"),
        (standard_id, "standard_script"),
        (must_read_id, "must_read"),
        (offline_id, "excluded"),
        (full_id, "excluded"),
        (None, None),
    ]
    question_ids = []
    for index, (related_content_id, _expected_type) in enumerate(relation_cases, start=1):
        created = client.post(
            "/api/admin/quiz-questions",
            json=quiz_payload(index, related_content_id=related_content_id),
            headers=admin_headers,
        )
        assert created.status_code == 201
        question_ids.append(created.json()["id"])

    response = client.get("/api/app/quiz", headers=general_user_headers)
    assert response.status_code == 200
    items_by_id = {item["id"]: item for item in response.json()["items"]}

    visible_question_ids = []
    excluded_question_ids = []
    for question_id, (related_content_id, expected_type) in zip(question_ids, relation_cases, strict=True):
        if expected_type == "excluded":
            excluded_question_ids.append(question_id)
            assert question_id not in items_by_id
            continue

        visible_question_ids.append(question_id)
        item = items_by_id[question_id]
        assert item["related_content_type"] == expected_type
        if expected_type is None:
            assert item["related_content_id"] is None
            assert item["related_content_title"] is None
        else:
            assert item["related_content_id"] == related_content_id

    assert "已下线关联内容" not in response.text
    assert "无权关联内容" not in response.text

    submitted = client.post(
        "/api/app/quiz/submit",
        json={
            "answers": [
                {"question_id": question_id, "selected_answer": "确认需求"}
                for question_id in visible_question_ids
            ]
        },
        headers=general_user_headers,
    )
    assert submitted.status_code == 200
    results_by_id = {item["question_id"]: item for item in submitted.json()["results"]}
    visible_cases = [
        (question_id, related_content_id, expected_type)
        for question_id, (related_content_id, expected_type) in zip(question_ids, relation_cases, strict=True)
        if expected_type != "excluded"
    ]
    for question_id, related_content_id, expected_type in visible_cases:
        result = results_by_id[question_id]
        assert result["related_content_type"] == expected_type
        assert result["related_content_id"] == (related_content_id if expected_type else None)

    for question_id in excluded_question_ids:
        rejected = client.post(
            "/api/app/quiz/submit",
            json={"answers": [{"question_id": question_id, "selected_answer": "确认需求"}]},
            headers=general_user_headers,
        )
        assert rejected.status_code == 404


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


def test_quiz_submit_accepts_an_enabled_visible_question_after_the_sampling_window_changes(
    client,
    admin_headers,
    full_user_headers,
    db_session,
):
    create_quiz_questions(client, admin_headers, 9, permission_level="general")
    originally_loaded = QuizQuestion(
        id=100,
        **quiz_payload(100, permission_level="full"),
    )
    db_session.add(originally_loaded)
    db_session.commit()

    loaded = client.get("/api/app/quiz", headers=full_user_headers)
    assert loaded.status_code == 200
    assert originally_loaded.id in {item["id"] for item in loaded.json()["items"]}

    earlier_reserved = QuizQuestion(
        id=50,
        **quiz_payload(50, permission_level="full"),
    )
    db_session.add(earlier_reserved)
    db_session.commit()

    reloaded = client.get("/api/app/quiz", headers=full_user_headers)
    assert reloaded.status_code == 200
    assert earlier_reserved.id in {item["id"] for item in reloaded.json()["items"]}
    assert originally_loaded.id not in {item["id"] for item in reloaded.json()["items"]}

    submitted = client.post(
        "/api/app/quiz/submit",
        json={
            "answers": [
                {
                    "question_id": originally_loaded.id,
                    "selected_answer": "确认需求",
                }
            ]
        },
        headers=full_user_headers,
    )

    assert submitted.status_code == 200
    assert submitted.json()["results"][0]["question_id"] == originally_loaded.id


def test_quiz_submit_rejects_questions_outside_current_user_permission(client, admin_headers, general_user_headers):
    question_ids = create_quiz_questions(client, admin_headers, 5, permission_level="full")

    response = client.post(
        "/api/app/quiz/submit",
        json={"answers": [{"question_id": question_ids[0], "selected_answer": "anything"}]},
        headers=general_user_headers,
    )

    assert response.status_code == 404


def test_quiz_submit_rejects_missing_and_disabled_questions(
    client,
    admin_headers,
    general_user_headers,
):
    disabled = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(1, status="disabled"),
        headers=admin_headers,
    )
    assert disabled.status_code == 201

    for question_id in (disabled.json()["id"], 999_999):
        response = client.post(
            "/api/app/quiz/submit",
            json={"answers": [{"question_id": question_id, "selected_answer": "确认需求"}]},
            headers=general_user_headers,
        )
        assert response.status_code == 404


@pytest.mark.parametrize("answer_count", [0, 11])
def test_quiz_submit_requires_one_to_ten_answers(
    client,
    admin_headers,
    general_user_headers,
    answer_count,
):
    question_id = create_quiz_questions(
        client,
        admin_headers,
        1,
        permission_level="general",
    )[0]

    response = client.post(
        "/api/app/quiz/submit",
        json={
            "answers": [
                {
                    "question_id": question_id,
                    "selected_answer": "确认需求",
                }
                for _index in range(answer_count)
            ]
        },
        headers=general_user_headers,
    )
    assert response.status_code == 422
