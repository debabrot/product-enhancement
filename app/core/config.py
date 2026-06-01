from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.exceptions import AgentProviderError


DEFAULT_GEMINI_MODEL = "gemini/gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class EnrichmentConfig(BaseSettings):
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
    gemini_model: str | None = Field(
        default=None,
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

    @field_validator("*", mode="before")
    @classmethod
    def _clean_env_value(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        cleaned = value.strip().strip('"').strip("'")
        return cleaned or None

    def enrichment_model(self, explicit_model: str | None = None) -> str:
        if explicit_model:
            return explicit_model

        for value in (
            self.enrichment_model_name,
            self.llm_model,
            self.gemini_model,
        ):
            if value:
                return value

        if self._has_openai_only_config():
            return DEFAULT_OPENAI_MODEL

        return DEFAULT_GEMINI_MODEL

    def validate_provider_config(self, model: str) -> None:
        model_name = model.lower()

        if model_name.startswith("gemini/") and not (
            self.gemini_api_key or self.google_api_key
        ):
            raise AgentProviderError(
                "No Gemini API key configured. Set GEMINI_API_KEY or GOOGLE_API_KEY, "
                "or set ENRICHMENT_MODEL/LLM_MODEL to an OpenAI model and configure "
                "OPENAI_API_KEY."
            )

        if (
            (model_name.startswith("gpt-") or model_name.startswith("openai/"))
            and not self.openai_api_key
        ):
            raise AgentProviderError(
                "No OpenAI API key configured. Set OPENAI_API_KEY, or set "
                "ENRICHMENT_MODEL/LLM_MODEL to a provider with configured credentials."
            )

    def _has_openai_only_config(self) -> bool:
        return bool(self.openai_api_key) and not (
            self.gemini_api_key or self.google_api_key
        )
