from test_admin_content_phase4 import base_payload, must_read_payload, standard_payload


def publish(client, admin_headers, payload):
    created = client.post("/api/admin/contents", json=payload, headers=admin_headers)
    assert created.status_code == 201
    response = client.post(f"/api/admin/contents/{created.json()['id']}/publish", headers=admin_headers)
    assert response.status_code == 200
    return response.json()["id"]


def test_must_read_list_is_sorted_and_permission_filtered(client, admin_headers, general_user_headers, full_user_headers):
    first_id = publish(client, admin_headers, must_read_payload(title="通用旧更新", permission_level="general"))
    second_id = publish(client, admin_headers, must_read_payload(title="全量新更新", permission_level="full"))

    general = client.get("/api/app/must-reads", headers=general_user_headers)
    assert general.status_code == 200
    assert [item["id"] for item in general.json()["items"]] == [first_id]

    full = client.get("/api/app/must-reads", headers=full_user_headers)
    assert full.status_code == 200
    assert [item["id"] for item in full.json()["items"]] == [second_id, first_id]


def test_must_read_detail_contains_required_fields_and_permission_error_does_not_leak(
    client,
    admin_headers,
    general_user_headers,
):
    full_id = publish(client, admin_headers, must_read_payload(title="全量更新", permission_level="full"))

    denied = client.get(f"/api/app/must-reads/{full_id}", headers=general_user_headers)
    assert denied.status_code == 403
    assert "全量更新" not in denied.text
    assert "本周统一使用新版接待口径" not in denied.text

    general_id = publish(client, admin_headers, must_read_payload(title="通用更新", permission_level="general"))
    detail = client.get(f"/api/app/must-reads/{general_id}", headers=general_user_headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["title"] == "通用更新"
    assert payload["update_body"]
    assert payload["adjustment_points"]
    assert payload["published_at"]
    assert payload["effective_at"]
    assert payload["permission_level"] == "general"


def test_standard_scripts_lists_categories_details_and_filters_by_scene(client, admin_headers, general_user_headers, full_user_headers):
    base_id = publish(client, admin_headers, base_payload(title="基础接待", permission_level="general"))
    standard_id = publish(client, admin_headers, standard_payload(title="全量价格异议", permission_level="full"))

    general = client.get("/api/app/scripts", headers=general_user_headers)
    assert general.status_code == 200
    assert [item["id"] for item in general.json()["base_scripts"]] == [base_id]
    assert general.json()["standard_scripts"] == []

    full = client.get("/api/app/scripts?category=价格", headers=full_user_headers)
    assert full.status_code == 200
    assert [item["id"] for item in full.json()["standard_scripts"]] == [standard_id]
    assert full.json()["standard_scripts"][0]["scene"] == "价格异议"
    assert full.json()["standard_scripts"][0]["recommended_speech_summary"]

    detail = client.get(f"/api/app/scripts/{standard_id}", headers=full_user_headers)
    assert detail.status_code == 200
    assert detail.json()["scene"] == "价格异议"
    assert detail.json()["recommended_speech"] == "先解释价值，再确认预算。"
    assert detail.json()["forbidden_speech"] == "不要直接降价。"
    assert detail.json()["copy_text"]

    denied = client.get(f"/api/app/scripts/{standard_id}", headers=general_user_headers)
    assert denied.status_code == 403
    assert "价格异议" not in denied.text
