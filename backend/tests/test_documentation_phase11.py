from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_local_development_document_covers_backend_frontend_dependencies_and_tests() -> None:
    document = read("docs/local-development.md")

    for required in [
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "MILVUS_HOST",
        "DASHSCOPE_API_KEY",
        "VITE_API_BASE_URL",
        "alembic upgrade head",
        "pnpm test:unit",
        "pnpm test:e2e",
        "pytest",
    ]:
        assert required in document


def test_baota_and_ecs_deployment_document_records_runtime_boundaries() -> None:
    document = read("docs/deployment-bt-ecs.md")

    for required in [
        "静态 HTML",
        "Nginx",
        "FastAPI",
        "127.0.0.1",
        "MySQL",
        "SQLAlchemy 不是数据库",
        "Milvus",
        "Docker",
        "DASHSCOPE_API_KEY",
        "前端不得直接调用",
    ]:
        assert required in document


def test_frontend_testing_manual_requires_real_mysql_milvus_dashscope_and_api_flow() -> None:
    document = read("docs/frontend-testing-manual.md")

    for required in [
        "USE_FAKE_EXTERNAL_CLIENTS=false",
        "MySQL",
        "Milvus",
        "DashScope",
        "DASHSCOPE_API_KEY",
        "管理员前端",
        "发布",
        "索引状态",
        "AI 问答",
        "未命中问题",
        "不得使用阶段 10 SQLite 夹具",
    ]:
        assert required in document
