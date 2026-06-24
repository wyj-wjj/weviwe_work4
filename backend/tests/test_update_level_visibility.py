from test_admin_content_phase4 import base_payload, must_read_payload


def test_admin_and_employee_content_payloads_expose_current_update_level(
    client,
    admin_headers,
    general_user_headers,
):
    created = client.post(
        "/api/admin/contents",
        json=must_read_payload(title="Visible update level", permission_level="general"),
        headers=admin_headers,
    )
    assert created.status_code == 201
    content_id = created.json()["id"]

    published = client.post(
        f"/api/admin/contents/{content_id}/publish",
        json={"update_level": "medium", "change_summary": "Visible medium update"},
        headers=admin_headers,
    )
    assert published.status_code == 200
    assert published.json()["current_update_level"] == "medium"

    admin_list = client.get("/api/admin/contents", headers=admin_headers)
    assert admin_list.status_code == 200
    admin_item = next(item for item in admin_list.json()["items"] if item["id"] == content_id)
    assert admin_item["current_version_no"] == 1
    assert admin_item["current_update_level"] == "medium"

    must_reads = client.get("/api/app/must-reads", headers=general_user_headers)
    assert must_reads.status_code == 200
    employee_item = next(item for item in must_reads.json()["items"] if item["id"] == content_id)
    assert employee_item["update_level"] == "medium"

    detail = client.get(f"/api/app/must-reads/{content_id}", headers=general_user_headers)
    assert detail.status_code == 200
    assert detail.json()["update_level"] == "medium"


def test_employee_script_and_rag_source_payloads_expose_update_level(
    client,
    admin_headers,
    general_user_headers,
):
    created = client.post(
        "/api/admin/contents",
        json=base_payload(
            title="Update level script source",
            permission_level="general",
            body="Update level script source body contains unique visibility text.",
        ),
        headers=admin_headers,
    )
    assert created.status_code == 201
    content_id = created.json()["id"]
    published = client.post(
        f"/api/admin/contents/{content_id}/publish",
        json={"update_level": "minor", "change_summary": "Copy edit only"},
        headers=admin_headers,
    )
    assert published.status_code == 200

    scripts = client.get("/api/app/scripts", headers=general_user_headers)
    assert scripts.status_code == 200
    script_item = next(item for item in scripts.json()["base_scripts"] if item["id"] == content_id)
    assert script_item["update_level"] == "minor"

    detail = client.get(f"/api/app/scripts/{content_id}", headers=general_user_headers)
    assert detail.status_code == 200
    assert detail.json()["update_level"] == "minor"

    answer = client.post(
        "/api/app/rag/ask",
        json={"question": "Update level script source visibility text"},
        headers=general_user_headers,
    )
    assert answer.status_code == 200
    assert any(
        source["content_id"] == content_id and source["update_level"] == "minor"
        for source in answer.json()["sources"]
    )
