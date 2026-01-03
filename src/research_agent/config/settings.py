"""Application settings loaded from environment variables."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # LLM Settings
    llm_provider: str = "anthropic"  # or "openai"
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    llm_model: str = "claude-sonnet-4-20250514"
    llm_temperature: float = 0.7

    # Tavily Settings
    tavily_api_key: str = ""
    tavily_search_depth: str = "advanced"
    tavily_max_results: int = 5

    # Research Defaults
    default_max_iterations: int = 7
    min_iterations: int = 5
    max_iterations: int = 15

    # Checkpointer Settings
    use_postgres: bool = False
    postgres_uri: Optional[str] = None

    # Logging
    log_level: str = "INFO"


settings = Settings()
