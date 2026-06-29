from sqlalchemy import select

from app.core.config import Settings
from app.integrations.dashscope import FakeDashScopeClient
from app.integrations.milvus import FakeMilvusClient
from app.models.content import Content, ContentChunk, ContentVersion
from app.models.user import User
from app.services.rag_answer_service import answer_question
from app.services.rag_index_service import sync_content_index
from test_admin_content_phase4 import base_payload
from test_quiz_phase5 import quiz_payload


def create_department(client, admin_headers, *, name: str, code: str) -> dict:
    response = client.post(
        "/api/admin/departments",
        json={"name": name, "code": code},
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


def create_employee(client, admin_headers, *, username: str, account_type: str, content_level: str, department_id: int):
    response = client.post(
        "/api/admin/users",
        json={
            "username": username,
            "password": "department-password",
            "display_name": username,
            "account_type": account_type,
            "content_level": content_level,
            "department_id": department_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


def login_headers(client, *, username: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "department-password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_published_content(client, admin_headers, **overrides) -> dict:
    response = client.post(
        "/api/admin/contents",
        json=base_payload(**overrides),
        headers=admin_headers,
    )
    assert response.status_code == 201
    content_id = response.json()["id"]
    published = client.post(f"/api/admin/contents/{content_id}/publish", headers=admin_headers)
    assert published.status_code == 200
    return published.json()


def test_admin_can_manage_departments_and_assign_enabled_department_to_employee(client, admin_headers):
    storage = create_department(client, admin_headers, name="储能事业部", code="storage")

    listing = client.get("/api/admin/departments", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["items"][0]["name"] == "储能事业部"

    edited = client.patch(
        f"/api/admin/departments/{storage['id']}",
        json={"name": "储能业务部"},
        headers=admin_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "储能业务部"

    disabled = client.post(f"/api/admin/departments/{storage['id']}/disable", headers=admin_headers)
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    rejected = client.post(
        "/api/admin/users",
        json={
            "username": "disabled-dept-user",
            "password": "department-password",
            "display_name": "disabled-dept-user",
            "account_type": "general_user",
            "content_level": "general",
            "department_id": storage["id"],
        },
        headers=admin_headers,
    )
    assert rejected.status_code == 422

    enabled = client.post(f"/api/admin/departments/{storage['id']}/enable", headers=admin_headers)
    assert enabled.status_code == 200
    user = create_employee(
        client,
        admin_headers,
        username="storage-general",
        account_type="general_user",
        content_level="general",
        department_id=storage["id"],
    )
    assert user["department_id"] == storage["id"]
    assert user["department_name"] == "储能业务部"


def test_content_scope_validation_and_version_chunk_snapshots(client, admin_headers, db_session):
    storage = create_department(client, admin_headers, name="储能事业部", code="storage")
    finance = create_department(client, admin_headers, name="财务部", code="finance")
    client.post(f"/api/admin/departments/{finance['id']}/disable", headers=admin_headers)

    missing_department = client.post(
        "/api/admin/contents",
        json=base_payload(scope_type="department", department_id=None),
        headers=admin_headers,
    )
    assert missing_department.status_code == 422

    global_with_department = client.post(
        "/api/admin/contents",
        json=base_payload(scope_type="global", department_id=storage["id"]),
        headers=admin_headers,
    )
    assert global_with_department.status_code == 422

    disabled_department = client.post(
        "/api/admin/contents",
        json=base_payload(scope_type="department", department_id=finance["id"]),
        headers=admin_headers,
    )
    assert disabled_department.status_code == 422

    published = create_published_content(
        client,
        admin_headers,
        title="储能部门消防话术",
        scope_type="department",
        department_id=storage["id"],
    )
    content = db_session.get(Content, published["id"])
    version = db_session.get(ContentVersion, published["current_version_id"])
    chunk = db_session.scalars(select(ContentChunk).where(ContentChunk.content_id == content.id)).one()

    assert published["scope_type"] == "department"
    assert published["department_id"] == storage["id"]
    assert content.scope_type == "department"
    assert content.department_id == storage["id"]
    assert version.scope_type == "department"
    assert version.department_id == storage["id"]
    assert chunk.scope_type == "department"
    assert chunk.department_id == storage["id"]


def test_employee_content_visibility_combines_department_scope_and_account_level(client, admin_headers):
    storage = create_department(client, admin_headers, name="储能事业部", code="storage")
    finance = create_department(client, admin_headers, name="财务部", code="finance")
    create_employee(
        client,
        admin_headers,
        username="storage-general-viewer",
        account_type="general_user",
        content_level="general",
        department_id=storage["id"],
    )
    create_employee(
        client,
        admin_headers,
        username="storage-full-viewer",
        account_type="full_user",
        content_level="full",
        department_id=storage["id"],
    )

    global_general = create_published_content(
        client,
        admin_headers,
        title="全公司通用基础话术",
        scope_type="global",
        department_id=None,
        permission_level="general",
    )
    storage_general = create_published_content(
        client,
        admin_headers,
        title="储能部门通用话术",
        scope_type="department",
        department_id=storage["id"],
        permission_level="general",
    )
    finance_general = create_published_content(
        client,
        admin_headers,
        title="财务部门通用话术",
        scope_type="department",
        department_id=finance["id"],
        permission_level="general",
    )
    storage_full = create_published_content(
        client,
        admin_headers,
        title="储能部门全量话术",
        scope_type="department",
        department_id=storage["id"],
        permission_level="full",
    )

    general = client.get(
        "/api/app/scripts",
        headers=login_headers(client, username="storage-general-viewer"),
    )
    assert general.status_code == 200
    general_ids = {item["id"] for item in general.json()["base_scripts"]}
    assert general_ids == {global_general["id"], storage_general["id"]}
    assert finance_general["title"] not in general.text
    assert storage_full["title"] not in general.text

    full = client.get(
        "/api/app/scripts",
        headers=login_headers(client, username="storage-full-viewer"),
    )
    assert full.status_code == 200
    full_ids = {item["id"] for item in full.json()["base_scripts"]}
    assert full_ids == {global_general["id"], storage_general["id"], storage_full["id"]}
    assert finance_general["title"] not in full.text


def test_rag_keyword_and_mysql_context_filter_department_scope(client, admin_headers, db_session):
    storage = create_department(client, admin_headers, name="储能事业部", code="storage")
    finance = create_department(client, admin_headers, name="财务部", code="finance")
    user_payload = create_employee(
        client,
        admin_headers,
        username="rag-storage-user",
        account_type="general_user",
        content_level="general",
        department_id=storage["id"],
    )
    storage_content = create_published_content(
        client,
        admin_headers,
        title="Storage fire safety",
        category="fire",
        body="fire safety answer for storage department only",
        structured_payload={"points": ["fire safety answer for storage department only"]},
        scope_type="department",
        department_id=storage["id"],
    )
    finance_content = create_published_content(
        client,
        admin_headers,
        title="Finance fire safety",
        category="fire",
        body="fire safety answer for finance department must not leak",
        structured_payload={"points": ["fire safety answer for finance department must not leak"]},
        scope_type="department",
        department_id=finance["id"],
    )

    user = db_session.get(User, user_payload["id"])
    result = answer_question(
        db_session,
        user=user,
        question="fire safety",
        dashscope_client=FakeDashScopeClient(embedding=[0.1, 0.2, 0.3]),
        milvus_client=FakeMilvusClient(search_results=[]),
        settings=Settings(rag_similarity_threshold=0.0),
    )

    assert result["hit"] is True
    assert [source["content_id"] for source in result["sources"]] == [storage_content["id"]]
    assert "storage department" in result["answer"]
    assert finance_content["title"] not in result["answer"]
    assert "finance department must not leak" not in result["answer"]


def test_milvus_metadata_and_search_request_include_department_scope(client, admin_headers, db_session):
    storage = create_department(client, admin_headers, name="储能事业部", code="storage")
    content = create_published_content(
        client,
        admin_headers,
        title="储能索引话术",
        scope_type="department",
        department_id=storage["id"],
    )

    milvus = FakeMilvusClient()
    sync_content_index(
        db_session,
        content_id=content["id"],
        dashscope_client=FakeDashScopeClient(embedding=[0.1, 0.2, 0.3]),
        milvus_client=milvus,
    )
    metadata = milvus.upsert_requests[-1][1][0].metadata
    assert metadata["scope_type"] == "department"
    assert metadata["department_id"] == storage["id"]

    milvus.search(collection_name="weview_scripts", query_vector=[0.1, 0.2, 0.3], allowed_permission_levels={"general"}, visible_department_id=storage["id"], top_k=5)
    assert milvus.search_requests[-1].visible_department_id == storage["id"]


def test_quiz_bound_to_content_follows_department_scope(client, admin_headers):
    storage = create_department(client, admin_headers, name="储能事业部", code="storage")
    finance = create_department(client, admin_headers, name="财务部", code="finance")
    create_employee(
        client,
        admin_headers,
        username="quiz-storage-user",
        account_type="general_user",
        content_level="general",
        department_id=storage["id"],
    )
    storage_content = create_published_content(
        client,
        admin_headers,
        title="储能测验来源",
        scope_type="department",
        department_id=storage["id"],
    )
    finance_content = create_published_content(
        client,
        admin_headers,
        title="财务测验来源",
        scope_type="department",
        department_id=finance["id"],
    )

    storage_question = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(1, related_content_id=storage_content["id"]),
        headers=admin_headers,
    )
    assert storage_question.status_code == 201
    finance_question = client.post(
        "/api/admin/quiz-questions",
        json=quiz_payload(2, related_content_id=finance_content["id"]),
        headers=admin_headers,
    )
    assert finance_question.status_code == 201

    quiz = client.get(
        "/api/app/quiz",
        headers=login_headers(client, username="quiz-storage-user"),
    )
    assert quiz.status_code == 200
    quiz_ids = {item["id"] for item in quiz.json()["items"]}
    assert storage_question.json()["id"] in quiz_ids
    assert finance_question.json()["id"] not in quiz_ids

    rejected = client.post(
        "/api/app/quiz/submit",
        json={"answers": [{"question_id": finance_question.json()["id"], "selected_answer": "确认需求"}]},
        headers=login_headers(client, username="quiz-storage-user"),
    )
    assert rejected.status_code == 404
