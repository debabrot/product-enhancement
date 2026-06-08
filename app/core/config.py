from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.exceptions import AgentProviderError


DEFAULT_GEMINI_MODEL = "gemini/gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENROUTER_FALLBACK_MODELS = (
    "deepseek/deepseek-r1:free",
    "qwen/qwen3-coder:free",
    "openrouter/free",
)
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore",
        populate_by_name=True,
    )

    enrichment_model_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ENRICHMENT_MODEL", "enrichment_model_name"),
    )
    llm_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_MODEL", "llm_model"),
    )
    gemini_model: str = Field(
        default="gemini/gemini-2.5-flash",
        validation_alias=AliasChoices("GEMINI_MODEL", "gemini_model"),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "gemini_api_key"),
    )
    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "google_api_key"),
    )
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "openrouter_api_key"),
    )
    openrouter_api_base: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices("OPENROUTER_API_BASE", "openrouter_api_base"),
    )
    openrouter_llm_model: str = Field(
        default="openrouter/deepseek/deepseek-v4-flash",
        validation_alias=AliasChoices("OPENROUTER_LLM_MODEL", "openrouter_llm_model")
    )
    log_level: str = Field(
        default="DEBUG",
        validation_alias=AliasChoices("LOG_LEVEL", "log_level"),
    )
    service_name: str = Field(
        default="product-enhancement-api",
        validation_alias=AliasChoices("OTEL_SERVICE_NAME", "otel_service_name"),
    )
    jaeger_endpoint: str = Field(
        default="DEBUG",
        validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_ENDPOINT", "otel_exporter_otlp_endpoint"),
    )

    @field_validator("*", mode="before")
    @classmethod
    def _clean_env_value(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        cleaned = value.strip().strip('"').strip("'")
        return cleaned or None

    @field_validator("log_level", mode="after")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed_levels:
            allowed = ", ".join(sorted(allowed_levels))
            raise ValueError(f"LOG_LEVEL must be one of: {allowed}.")

        return normalized

    def _as_litellm_openrouter_model(self, model: str) -> str:
        model_name = model.strip()
        if model_name.startswith("openrouter/openrouter/"):
            return model_name

        return f"openrouter/{model_name}"

    def _has_openai_only_config(self) -> bool:
        return bool(self.openai_api_key) and not (
            self.gemini_api_key or self.google_api_key
        )
