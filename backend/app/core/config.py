from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CivicOps Agent"
    app_version: str = "1.0.0"
    environment: str = "local"
    database_url: str = "sqlite:///./civicops.db"
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    llm_provider: str = "mock"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    embedding_provider: str = "bge"
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    embedding_batch_size: int = 64
    embedding_cache_dir: str | None = None
    embedding_query_instruction: str = "Represent this sentence for searching relevant passages: "
    nyc_311_endpoint: str = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
    rag_include_remote_sources: bool = False
    rag_remote_timeout_seconds: int = 35
    rag_remote_concurrency: int = 6
    rag_max_311_articles: int = 120
    ingestion_sync_limit: int = 5000
    ingestion_sync_lookback_days: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
