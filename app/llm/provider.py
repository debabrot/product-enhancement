from __future__ import annotations

from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


class LLMProviderProtocol(Protocol):
    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict[str, Any] | None = None,
    ) -> object:
        """Return a chat completion response from the configured LLM backend."""


class LLMProvider:
    """
    Unified LLM provider backed by LiteLLM.

    Supports any LiteLLM-compatible model string, including:
      - OpenAI:      "gpt-4o"
      - Anthropic:   "anthropic/claude-3-5-sonnet-20241022"
      - OpenRouter:  "openrouter/openai/gpt-4o"
                     "openrouter/anthropic/claude-3-5-sonnet"
      - Azure:       "azure/<your-deployment-name>"
      - AWS Bedrock: "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"

    API keys are resolved in this order:
      1. Explicit `api_key` constructor argument
      2. LiteLLM's automatic env-var lookup per provider
         (OPENAI_API_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, etc.)
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        # Extra provider-specific params (e.g. {"reasoning_effort": "low"})
        self.extra_params: dict[str, Any] = extra_params or {}

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict[str, Any] | None = None,
    ) -> object:
        import litellm

        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            **self.extra_params,
        }

        if self.api_key:
            request["api_key"] = self.api_key
        if self.api_base:
            request["api_base"] = self.api_base
        if response_format is not None:
            request["response_format"] = response_format

        logger.debug(
            "llm_request",
            model=self.model,
            message_count=len(messages),
            temperature=temperature,
        )

        try:
            response = await litellm.acompletion(**request)
        except litellm.exceptions.AuthenticationError as exc:
            logger.error("llm_auth_error", model=self.model, error=str(exc))
            raise
        except litellm.exceptions.RateLimitError as exc:
            logger.error("llm_rate_limit", model=self.model, error=str(exc))
            raise
        except litellm.exceptions.BadRequestError as exc:
            logger.error("llm_bad_request", model=self.model, error=str(exc))
            raise
        except Exception as exc:
            logger.error("llm_error", model=self.model, error=str(exc))
            raise

        logger.debug(
            "llm_response",
            model=self.model,
            usage=getattr(response, "usage", None),
        )

        return response