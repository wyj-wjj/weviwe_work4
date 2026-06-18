from sqlalchemy import select

from app.domain.enums import ContentStatus
from app.models.content import Content, ContentVersion
from app.services.content_service import list_ai_searchable_chunks, publish_content


def base_payload(**overrides):
    payload = {
        "content_type": "base_script",
        "title": "通用接待话术",
        "category": "接待",
        "permission_level": "general",
        "summary": "接待时保持一致口径",
        "body": "请先问候客户，再确认需求。",
        "structured_payload": {"points": ["问候客户", "确认需求"]},
    }
    payload.update(overrides)
    return payload


def standard_payload(**overrides):
    payload = base_payload(
        content_type="standard_script",
        title="价格异议处理",
        category="价格",
        permission_level="full",
        body="推荐说法：先解释价值，再确认预算。",
        structured_payload={
            "scene": "价格异议",
            "recommended_speech": "先解释价值，再确认预算。",
            "forbidden_speech": "不要直接降价。",
            "notes": "保持专业。",
        },
    )
    payload.update(overrides)
    return payload


def must_read_payload(**overrides):
    payload = base_payload(
        content_type="must_read",
        title="本周口径更新",
        category="公告",
        body="本周统一使用新版接待口径。",
        structured_payload={
            "update_body": "本周统一使用新版接待口径。",
            "adjustment_points": ["先确认客户身份", "再进入业务沟通"],
        },
    )
    payload.update(overrides)
    return payload


def test_admin_can_create_draft_non_admin_is_rejected_and_type_specific_fields_are_validated(
    client,
    admin_headers,
    full_user_headers,
):
    created = client.post("/api/admin/contents", json=base_payload(), headers=admin_headers)
    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert created.json()["current_version_id"] is None

    rejected = client.post("/api/admin/contents", json=base_payload(title="员工误操作"), headers=full_user_headers)
    assert rejected.status_code == 403

    missing_scene = client.post(
        "/api/admin/contents",
        json=standard_payload(structured_payload={"recommended_speech": "缺场景"}),
        headers=admin_headers,
    )
    assert missing_scene.status_code == 422

    missing_update = client.post(
        "/api/admin/contents",
        json=must_read_payload(structured_payload={"adjustment_points": ["缺正文"]}),
        headers=admin_headers,
    )
    assert missing_update.status_code == 422


def test_admin_content_list_filters_paginates_and_editing_draft_does_not_create_version(client, admin_headers, db_session):
    first = client.post("/api/admin/contents", json=base_payload(title="A", category="接待"), headers=admin_headers).json()
    client.post("/api/admin/contents", json=standard_payload(title="B", category="价格"), headers=admin_headers)

    filtered = client.get(
        "/api/admin/contents?content_type=base_script&status=draft&permission_level=general&category=接待&page=1&page_size=10",
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["title"] == "A"

    edited = client.patch(
        f"/api/admin/contents/{first['id']}",
        json={"title": "A edited", "body": "编辑后的草稿正文。"},
        headers=admin_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "A edited"
    assert db_session.scalars(select(ContentVersion)).all() == []


def test_publish_republish_preserves_history_and_sets_publish_times(client, admin_headers, db_session):
    content_id = client.post("/api/admin/contents", json=base_payload(), headers=admin_headers).json()["id"]

    first = publish_content(db_session, content_id=content_id)
    assert first.version_no == 1
    assert first.published_at is not None
    assert first.effective_at == first.published_at

    client.patch(
        f"/api/admin/contents/{content_id}",
        json={"body": "第二版正文。", "summary": "第二版摘要"},
        headers=admin_headers,
    )
    second = publish_content(db_session, content_id=content_id)

    db_session.refresh(first)
    content = db_session.get(Content, content_id)
    assert second.version_no == 2
    assert content.status == ContentStatus.PUBLISHED.value
    assert content.current_version_id == second.id
    assert first.body == "请先问候客户，再确认需求。"
    assert second.body == "第二版正文。"


def test_admin_detail_offline_history_and_employee_draft_or_offline_invisibility(
    client,
    admin_headers,
    general_user_headers,
):
    draft_id = client.post("/api/admin/contents", json=must_read_payload(), headers=admin_headers).json()["id"]

    draft_list = client.get("/api/app/must-reads", headers=general_user_headers)
    assert draft_list.status_code == 200
    assert draft_list.json()["items"] == []

    published = client.post(f"/api/admin/contents/{draft_id}/publish", headers=admin_headers)
    assert published.status_code == 200
    assert published.json()["current_version_no"] == 1

    detail = client.get(f"/api/admin/contents/{draft_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["index_status"] == "synced"
    assert detail.json()["current_version_id"] == published.json()["current_version_id"]

    employee_list = client.get("/api/app/must-reads", headers=general_user_headers)
    assert len(employee_list.json()["items"]) == 1

    history = client.get(f"/api/admin/contents/{draft_id}/versions", headers=admin_headers)
    assert history.status_code == 200
    assert history.json()["items"][0]["version_no"] == 1

    employee_history = client.get(f"/api/admin/contents/{draft_id}/versions", headers=general_user_headers)
    assert employee_history.status_code == 403

    offline = client.post(f"/api/admin/contents/{draft_id}/offline", headers=admin_headers)
    assert offline.status_code == 200
    assert offline.json()["status"] == "offline"

    hidden = client.get("/api/app/must-reads", headers=general_user_headers)
    assert hidden.json()["items"] == []


def test_offline_content_chunks_are_excluded_from_ai_candidates(client, admin_headers, db_session):
    content_id = client.post("/api/admin/contents", json=base_payload(), headers=admin_headers).json()["id"]
    client.post(f"/api/admin/contents/{content_id}/publish", headers=admin_headers)

    assert len(list_ai_searchable_chunks(db_session)) == 1

    client.post(f"/api/admin/contents/{content_id}/offline", headers=admin_headers)
    assert list_ai_searchable_chunks(db_session) == []
