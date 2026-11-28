"""Application settings loaded from environment / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = "sqlite:///./invoiceflow.db"

    # LLM (opencode-go collection, OpenAI-compatible chat dialect)
    opencode_base_url: str = "https://opencode.ai/zen/go/v1"
    opencode_api_key: str = ""
    opencode_session: str = "invoiceflow-dev"

    # Offline deterministic stub — no network, used by CI and `pytest`
    llm_stub: bool = False

    # LLM resilience (env-overridable): bounded retries + backoff + per-call timeout
    llm_max_attempts: int = 3
    llm_backoff_base_seconds: float = 0.5
    llm_timeout_seconds: float = 60.0

    # Per-agent model routing
    llm_vision_model: str = "deepseek-v4.1-flash"
    llm_reasoning_model: str = "deepseek-v4-pro"
    llm_classify_model: str = "qwen3.8-flash"

    # OCR
    tesseract_path: str = "/usr/bin/tesseract"

    # App
    cors_origins: str = "http://localhost:3000"
    secret_key: str = "change-me"

    # Processing thresholds
    low_confidence_threshold: float = 0.7

    # Maintenance endpoints (POST /api/maintenance/reset-e2e) are disabled
    # unless this is set; callers must present it in the X-E2E-Token header.
    e2e_reset_token: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def uses_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
