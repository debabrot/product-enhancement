from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, str] | None = None,
    ) -> object:
        """Return a chat completion response from the configured LLM backend."""


class LiteLLMProvider:
    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, str] | None = None,
    ) -> object:
        import litellm

        return litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format=response_format,
        )
