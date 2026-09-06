from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_prefix="AGENT_EVAL_", env_file=".env")

    database_url: str = "postgresql+psycopg://localhost/agent_eval_dev"

    # Runner defaults (docs/architecture.md "timeout boundary")
    adapter_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
