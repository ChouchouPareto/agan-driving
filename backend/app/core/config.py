from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret: str = "development-only-change-me"
    database_url: str = "sqlite:///../data/app.db"
    dify_base_url: str = ""
    dify_api_key: str = ""
    dify_workflow_id: str = ""
    main_model_id: str = "mock-main"
    model_timeout_seconds: int = 30
    model_max_retries: int = 1
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    @property
    def mock_ai(self) -> bool:
        return not (self.dify_base_url and self.dify_api_key and self.dify_workflow_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
