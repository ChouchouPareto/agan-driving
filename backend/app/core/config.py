from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret: str = "development-only-change-me"
    staff_invitation_code: str = "INVITE_CODE_REMOVED"
    rag_enabled: bool = True
    rag_storage_dir: str = "../data/rag"
    rag_collection_prefix: str = "driving_school_subject1"
    embedding_model_id: str = "text-embedding-v4"
    embedding_dimensions: int = 1024
    rerank_model_id: str = "qwen3-rerank"
    rag_vector_top_k: int = 20
    rag_keyword_top_k: int = 20
    rag_rerank_top_k: int = 5
    rag_model_timeout_seconds: int = 20
    rag_max_retries: int = 2
    database_url: str = "sqlite:///../data/app.db"
    dify_base_url: str = ""
    dify_api_key: str = ""
    dify_workflow_id: str = ""
    main_model_id: str = "mock-main"
    model_timeout_seconds: int = 30
    model_max_retries: int = 1
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ocr_model_id: str = "qwen-vl-ocr"
    ocr_storage_dir: str = "../data/private-assets"
    ocr_max_image_bytes: int = 10 * 1024 * 1024
    ocr_max_pixels: int = 24_000_000
    ocr_retention_days: int = 7
    ocr_low_confidence_threshold: float = 0.85
    ocr_max_retries: int = 2
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    @property
    def mock_ai(self) -> bool:
        return not (self.dify_base_url and self.dify_api_key and self.dify_workflow_id)

    @property
    def mock_ocr(self) -> bool:
        return not self.dashscope_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
