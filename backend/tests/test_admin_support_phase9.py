from app.models.content import Content
from app.models.quiz import QuizQuestion


def test_admin_quiz_list_exposes_related_content_and_updated_at(client, admin_headers, db_session):
    content = Content(
        content_type="base_script",
        title="关联基础话术",
        category="接待",
        permission_level="general",
        status="draft",
        index_status="not_synced",
        draft_body="先确认客户需求。",
        created_by=1,
    )
    db_session.add(content)
    db_session.flush()
    question = QuizQuestion(
        question="应该先做什么？",
        options=["确认需求", "直接报价"],
        answer="确认需求",
        explanation="先确认需求。",
        related_content_id=content.id,
        permission_level="general",
        status="enabled",
    )
    db_session.add(question)
    db_session.commit()

    response = client.get("/api/admin/quiz-questions", headers=admin_headers)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["related_content_title"] == "关联基础话术"
    assert item["updated_at"]


def test_content_history_exposes_publisher_display_name(client, admin_headers):
    created = client.post(
        "/api/admin/contents",
        json={
            "content_type": "base_script",
            "title": "历史发布人测试",
            "category": "接待",
            "permission_level": "general",
            "summary": "摘要",
            "body": "正文",
            "structured_payload": {"points": ["摘要"]},
        },
        headers=admin_headers,
    )
    content_id = created.json()["id"]
    client.post(f"/api/admin/contents/{content_id}/publish", headers=admin_headers)

    response = client.get(f"/api/admin/contents/{content_id}/versions", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["items"][0]["created_by_name"] == "admin-user 显示名"
