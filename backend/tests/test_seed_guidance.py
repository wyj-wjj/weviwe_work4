from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_initial_admin_seed_guidance_requires_operator_supplied_password() -> None:
    docs = (ROOT / "docs" / "initial-admin.md").read_text(encoding="utf-8")

    assert "INITIAL_ADMIN_PASSWORD" in docs
    assert "环境变量" in docs
    assert "不要提交" in docs
    assert "真实密码" not in docs.replace("不得在仓库保存真实密码", "")
