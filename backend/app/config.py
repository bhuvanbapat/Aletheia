"""Application configuration via environment variables with safe defaults."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Aletheia settings. Secrets are only ever provided via environment."""

    app_name: str = "Aletheia"
    environment: str = "demo"
    database_url: str = "sqlite:///./aletheia.db"

    # LLM provider (OpenAI-compatible). api_key is never hard-coded.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "mock"
    llm_timeout_seconds: float = 30.0

    # Agent loop safety limits
    agent_max_tool_calls: int = 40
    agent_max_repeated_calls: int = 3
    agent_max_runtime_seconds: int = 120

    # Remediation control: analysis | recommend | approval_required | simulation | execute
    remediation_mode: str = "approval_required"

    # Telemetry / synthetic environment
    synthetic_seed: int = 42

    model_config = {"env_prefix": "ALETHEIA_", "env_file": ".env", "extra": "ignore"}

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model != "mock")


@lru_cache
def get_settings() -> Settings:
    return Settings()


