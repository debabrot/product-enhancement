from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values

from app.exceptions import AgentProviderError, AgentResponseError
from app.schemas.enrich import EnrichmentRequestSchema, EnrichmentResponseSchema


DEFAULT_GEMINI_MODEL = "gemini/gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
MODEL_ENV_VARS = ("ENRICHMENT_MODEL", "LLM_MODEL", "GEMINI_MODEL")
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class EnrichmentAgent:
    def __init__(self, model: str | None = None) -> None:
        self._model_is_explicit = model is not None
        self._process_env = {
            env_var: os.getenv(env_var)
            for env_var in (
                *MODEL_ENV_VARS,
                "OPENAI_API_KEY",
                "GEMINI_API_KEY",
                "GOOGLE_API_KEY",
            )
        }
        self._file_env = dotenv_values(ENV_FILE)
        self.model = model or self._configured_model()

    def enrich(self, request: EnrichmentRequestSchema) -> EnrichmentResponseSchema:
        self._validate_provider_config()

        try:
            import litellm

            response = litellm.completion(
                model=self.model,
                messages=self._build_messages(request),
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise AgentProviderError(
                f"LLM enrichment request failed for model {self.model!r}: {exc}"
            ) from exc

        content = self._extract_content(response)
        payload = self._parse_json(content)

        try:
            return EnrichmentResponseSchema.model_validate(payload)
        except Exception as exc:
            raise AgentResponseError("LLM returned an invalid enrichment schema.") from exc

    def _build_messages(self, request: EnrichmentRequestSchema) -> list[dict[str, str]]:
        product_json = request.model_dump_json(indent=2)
        return [
            {
                "role": "system",
                "content": (
                    "You enrich product data for a marketplace POC. "
                    "Return JSON only with exactly these top-level keys: "
                    "product_code, description, attributes. Keep product_code unchanged. "
                    "Improve the description using the user instructions and existing "
                    "attributes. Add or refine attributes only when the input supports it."
                ),
            },
            {
                "role": "user",
                "content": f"Enrich this product:\n{product_json}",
            },
        ]

    def _extract_content(self, response: object) -> str:
        if isinstance(response, Mapping):
            choices = response.get("choices")
        else:
            choices = getattr(response, "choices", None)

        if not choices:
            raise AgentResponseError("LLM returned no choices.")

        first_choice = choices[0]
        if isinstance(first_choice, Mapping):
            message = first_choice.get("message", {})
        else:
            message = getattr(first_choice, "message", {})

        if isinstance(message, Mapping):
            content = message.get("content")
        else:
            content = getattr(message, "content", None)

        if not isinstance(content, str) or not content.strip():
            raise AgentResponseError("LLM returned empty content.")

        return content

    def _parse_json(self, content: str) -> dict[str, object]:
        clean_content = self._strip_json_fence(content)
        try:
            payload = json.loads(clean_content)
        except json.JSONDecodeError as exc:
            raise AgentResponseError("LLM returned non-JSON content.") from exc

        if not isinstance(payload, dict):
            raise AgentResponseError("LLM JSON response must be an object.")

        return payload

    def _strip_json_fence(self, content: str) -> str:
        stripped = content.strip()
        if not stripped.startswith("```"):
            return stripped

        lines = stripped.splitlines()
        if len(lines) < 3:
            return stripped

        return "\n".join(lines[1:-1]).strip()

    def _configured_model(self) -> str:
        for env_var in MODEL_ENV_VARS:
            value = self._clean_env_value(self._process_env.get(env_var))
            if value:
                return value

        if self._clean_env_value(self._process_env.get("OPENAI_API_KEY")) and not (
            self._clean_env_value(self._process_env.get("GEMINI_API_KEY"))
            or self._clean_env_value(self._process_env.get("GOOGLE_API_KEY"))
        ):
            return DEFAULT_OPENAI_MODEL

        for env_var in MODEL_ENV_VARS:
            value = self._clean_env_value(self._file_env.get(env_var))
            if value:
                return value

        if self._clean_env_value(self._file_env.get("OPENAI_API_KEY")) and not (
            self._clean_env_value(self._file_env.get("GEMINI_API_KEY"))
            or self._clean_env_value(self._file_env.get("GOOGLE_API_KEY"))
        ):
            return DEFAULT_OPENAI_MODEL

        return DEFAULT_GEMINI_MODEL

    def _validate_provider_config(self) -> None:
        model_name = self.model.lower()

        if model_name.startswith("gemini/") and not (
            self._provider_config_value("GEMINI_API_KEY")
            or self._provider_config_value("GOOGLE_API_KEY")
        ):
            raise AgentProviderError(
                "No Gemini API key configured. Set GEMINI_API_KEY or GOOGLE_API_KEY, "
                "or set ENRICHMENT_MODEL/LLM_MODEL to an OpenAI model and configure "
                "OPENAI_API_KEY."
            )

        if (
            (model_name.startswith("gpt-") or model_name.startswith("openai/"))
            and not self._provider_config_value("OPENAI_API_KEY")
        ):
            raise AgentProviderError(
                "No OpenAI API key configured. Set OPENAI_API_KEY, or set "
                "ENRICHMENT_MODEL/LLM_MODEL to a provider with configured credentials."
            )

    def _provider_config_value(self, env_var: str) -> str | None:
        if self._model_is_explicit:
            return self._clean_env_value(self._process_env.get(env_var))

        return self._config_value(env_var)

    def _config_value(self, env_var: str) -> str | None:
        return self._clean_env_value(self._process_env.get(env_var)) or self._clean_env_value(
            self._file_env.get(env_var)
        )

    def _clean_env_value(self, value: str | None) -> str | None:
        if not value:
            return None

        cleaned = value.strip().strip('"').strip("'")
        return cleaned or None
