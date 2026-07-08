from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "weview-work4-api"
    database_url: str = "mysql+pymysql://weview_user:local_placeholder@localhost:3306/weview_mvp"
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection_name: str = "weview_content_chunks"
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_chat_model: str = "qwen-plus"
    dashscope_structure_model: str = "qwen-plus"
    dashscope_quiz_model: str = "qwen-plus"
    dashscope_embedding_model: str = "text-embedding-v4"
    dashscope_ocr_model: str = "qwen-vl-ocr-2025-11-20"
    dashscope_vision_model: str = "qwen3.6-plus"
    dashscope_http_timeout_seconds: float = 30.0
    dashscope_import_timeout_seconds: float = 300.0
    dashscope_ocr_timeout_seconds: float = 120.0
    dashscope_quiz_timeout_seconds: float = 90.0
    content_import_max_file_mb: int = 20
    content_import_max_pdf_pages: int = 80
    content_import_max_ocr_pages: int = 30
    content_import_default_parse_mode: str = "fast"
    rag_similarity_threshold: float = 0.65
    rag_top_k: int = 5
    jwt_secret_key: str = "test-only-insecure-secret-with-32-plus-chars"
    use_fake_external_clients: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
