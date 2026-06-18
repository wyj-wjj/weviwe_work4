from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase_0_guardrail_note_records_constraints_and_worktree_boundaries() -> None:
    note = (ROOT / "docs" / "phase-0-guardrails.md").read_text(encoding="utf-8")

    required_constraints = [
        "MySQL 是唯一权威数据源",
        "Milvus 只作为向量检索索引",
        "权限校验以后端为准",
        "未命中时模型不得自由回答",
        "MVP 不引入复杂中间件",
    ]
    for constraint in required_constraints:
        assert constraint in note

    assert "memory-bank/implementation-plan.md" in note
    assert "image/" in note
    assert "不得触碰" in note
    assert "backend/" in note
    assert "frontend/" in note
    assert "infra/" in note
    assert ".env.example" in note


def test_phase_0_milestones_map_to_mvp_acceptance_criteria() -> None:
    note = (ROOT / "docs" / "phase-0-guardrails.md").read_text(encoding="utf-8")

    for milestone in ["后端", "前端", "RAG", "端到端", "部署文档"]:
        assert milestone in note

    for criterion_number in ["验收 1", "验收 4", "验收 5", "验收 10", "验收 14"]:
        assert criterion_number in note


def test_phase_0_test_strategy_covers_required_backend_frontend_and_external_boundaries() -> None:
    note = (ROOT / "docs" / "phase-0-guardrails.md").read_text(encoding="utf-8")

    backend_topics = ["登录", "权限过滤", "内容发布", "版本管理", "索引失败", "AI 未命中", "来源一致性"]
    frontend_topics = ["员工登录", "管理员登录", "后台路由限制", "通用用户可见性", "完整权限用户可见性", "AI 未命中界面"]
    external_topics = ["假 DashScope 客户端", "假 Milvus 客户端", "真实模型调用", "手动冒烟检查"]

    for topic in backend_topics + frontend_topics + external_topics:
        assert topic in note


def test_local_development_docs_explain_runtime_dependencies_and_startup_checks() -> None:
    local_docs = (ROOT / "docs" / "local-development.md").read_text(encoding="utf-8")
    infra_docs = (ROOT / "infra" / "local-services.md").read_text(encoding="utf-8")
    text = f"{local_docs}\n{infra_docs}"

    for expected in [
        "MySQL 主机",
        "数据库名",
        "Milvus 主机",
        "Milvus 端口",
        "本地密钥",
        "后端健康检查",
        "前端路由加载",
        "MySQL 连通性",
        "Milvus 连通性",
    ]:
        assert expected in text


def test_env_example_contains_required_names_and_no_real_secret_values() -> None:
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")
    values_by_name: dict[str, str] = {}
    for raw_line in env_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, value = line.split("=", 1)
        values_by_name[name] = value

    required_names = {
        "DATABASE_URL",
        "MILVUS_HOST",
        "MILVUS_PORT",
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_BASE_URL",
        "DASHSCOPE_CHAT_MODEL",
        "DASHSCOPE_EMBEDDING_MODEL",
        "JWT_SECRET_KEY",
        "USE_FAKE_EXTERNAL_CLIENTS",
        "VITE_API_BASE_URL",
    }
    assert required_names <= values_by_name.keys()

    suspicious_fragments = ["sk-", "AKIA", "eyJ", "dashscope-real", "prod-", "password123"]
    for name, value in values_by_name.items():
        assert all(fragment not in value for fragment in suspicious_fragments), name
        assert "192.168." not in value and "10." not in value, name
