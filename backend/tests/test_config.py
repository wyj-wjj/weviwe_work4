from app.core.config import Settings


def test_settings_load_test_safe_defaults_without_real_secrets(monkeypatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.service_name == "weview-work4-api"
    assert settings.database_url.startswith("mysql+pymysql://")
    assert settings.milvus_host == "localhost"
    assert settings.milvus_port == 19530
    assert settings.dashscope_api_key == ""
    assert settings.dashscope_chat_model == "qwen-plus"
    assert settings.dashscope_embedding_model == "text-embedding-v4"
    assert settings.jwt_secret_key == "test-only-insecure-secret-with-32-plus-chars"
    assert settings.use_fake_external_clients is True
