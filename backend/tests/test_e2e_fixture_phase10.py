from sqlalchemy import select

from app.api.deps import get_dashscope_client, get_milvus_client
from app.e2e_fixture import (
    E2E_ADMIN_USERNAME,
    E2E_FULL_USERNAME,
    E2E_GENERAL_USERNAME,
    E2E_MISS_QUESTION,
    E2E_PASSWORD,
    build_e2e_clients,
    seed_e2e_fixture,
)
from app.main import app
from app.models.content import VectorIndexRecord


def login(client, username: str) -> tuple[dict[str, str], dict]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": E2E_PASSWORD},
    )
    assert response.status_code == 200
    payload = response.json()
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload["user"]


def test_phase10_fixture_prepares_accounts_content_quiz_and_deterministic_rag(
    client,
    db_session,
) -> None:
    dashscope_client, milvus_client = build_e2e_clients()
    summary = seed_e2e_fixture(
        db_session,
        dashscope_client=dashscope_client,
        milvus_client=milvus_client,
    )
    app.dependency_overrides[get_dashscope_client] = lambda: dashscope_client
    app.dependency_overrides[get_milvus_client] = lambda: milvus_client

    admin_headers, admin = login(client, E2E_ADMIN_USERNAME)
    full_headers, full_user = login(client, E2E_FULL_USERNAME)
    general_headers, general_user = login(client, E2E_GENERAL_USERNAME)

    assert (admin["account_type"], admin["content_level"]) == ("admin", "full")
    assert (full_user["account_type"], full_user["content_level"]) == ("full_user", "full")
    assert (general_user["account_type"], general_user["content_level"]) == (
        "general_user",
        "general",
    )

    general_must_reads = client.get("/api/app/must-reads", headers=general_headers).json()["items"]
    full_must_reads = client.get("/api/app/must-reads", headers=full_headers).json()["items"]
    assert {item["title"] for item in general_must_reads} == {"E2E 通用最新必读"}
    assert {item["title"] for item in full_must_reads} == {
        "E2E 通用最新必读",
        "E2E 全量最新必读",
    }

    general_scripts = client.get("/api/app/scripts", headers=general_headers).json()
    full_scripts = client.get("/api/app/scripts", headers=full_headers).json()
    assert len(general_scripts["base_scripts"]) == 1
    assert len(general_scripts["standard_scripts"]) == 1
    assert len(full_scripts["base_scripts"]) == 2
    assert len(full_scripts["standard_scripts"]) == 2

    general_quiz = client.get("/api/app/quiz", headers=general_headers).json()["items"]
    full_quiz = client.get("/api/app/quiz", headers=full_headers).json()["items"]
    assert len(general_quiz) == 5
    assert all("全量" not in item["question"] for item in general_quiz)
    assert any("全量" in item["question"] for item in full_quiz)

    hit = client.post(
        "/api/app/rag/ask",
        json={"question": "客户开场应该怎么说？"},
        headers=general_headers,
    )
    assert hit.status_code == 200
    hit_payload = hit.json()
    assert hit_payload["hit"] is True
    assert hit_payload["usage"] == {"mode": "fast_extractive"}
    assert "根据当前已发布且有权限的话术资料" in hit_payload["answer"]
    assert "E2E 通用" in hit_payload["answer"]
    assert "E2E 全量" not in hit_payload["answer"]
    assert hit_payload["sources"]
    assert all("全量" not in source["title"] for source in hit_payload["sources"])

    missed = client.post(
        "/api/app/rag/ask",
        json={"question": E2E_MISS_QUESTION},
        headers=general_headers,
    )
    assert missed.status_code == 200
    assert missed.json() == {
        "hit": False,
        "answer": "当前没有有效标准口径，请联系管理员。",
        "sources": [],
    }
    missed_listing = client.get("/api/admin/missed-questions", headers=admin_headers)
    assert missed_listing.status_code == 200
    assert E2E_MISS_QUESTION in {item["question"] for item in missed_listing.json()["items"]}

    assert summary["content_count"] == 6
    assert summary["quiz_count"] == 6
    assert len(db_session.scalars(select(VectorIndexRecord)).all()) == 6
