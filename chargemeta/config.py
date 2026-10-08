from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ChargeMeta Agent"
    database_url: str = "sqlite:///./chargemeta.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = True
    llm_provider: str = "mock"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    bailian_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    bailian_api_key: str = ""
    bailian_model: str = "qwen-plus"
    sample_limit: int = 20
    auto_publish_threshold: float = 0.85
    review_threshold: float = 0.60
    embedding_provider: str = "hash"
    ollama_embedding_model: str = "bge-m3"
    embedding_dimension: int = 384
    governance_max_retries: int = 1
    quality_min_average_confidence: float = 0.72
    quality_max_pending_ratio: float = 0.75
    relation_min_confidence: float = 0.78
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
