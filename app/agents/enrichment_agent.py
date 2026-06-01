from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Literal, TypedDict, cast, overload

from langgraph.graph import END, START, StateGraph

from app.core.config import EnrichmentConfig
from app.exceptions import AgentProviderError, AgentResponseError
from app.llm.provider import LLMProvider
from app.schemas.enrich import EnrichmentRequestSchema, EnrichmentResponseSchema


class EnrichmentAgentState(TypedDict, total=False):
    request: EnrichmentRequestSchema
    enrichment: dict[str, object]
    critique: dict[str, object]
    attempts: int


class EnrichmentAgent:
    def __init__(
        self,
        *,
        model: str,
        llm_provider: LLMProvider,
        enrichment_config: EnrichmentConfig | None = None,
        max_reflection_attempts: int = 1,
    ) -> None:
        self.model = model
        self.llm_provider = llm_provider
        self.enrichment_config = enrichment_config
        self.max_reflection_attempts = max_reflection_attempts
        self._graph = self._build_graph()

    def enrich(self, request: EnrichmentRequestSchema) -> EnrichmentResponseSchema:
        if self.enrichment_config:
            self.enrichment_config.validate_provider_config(self.model)

        try:
            final_state = self._graph.invoke({"request": request, "attempts": 0})
        except Exception as exc:
            if isinstance(exc, AgentResponseError):
                raise exc
            raise AgentProviderError(
                f"LLM enrichment request failed for model {self.model!r}: {exc}"
            ) from exc

        payload = final_state.get("enrichment")
        if not isinstance(payload, dict):
            raise AgentResponseError("Enrichment agent did not produce JSON output.")

        payload["product_code"] = request.product_code

        try:
            return EnrichmentResponseSchema.model_validate(payload)
        except Exception as exc:
            raise AgentResponseError("LLM returned an invalid enrichment schema.") from exc

    def _build_graph(self):
        graph = StateGraph(EnrichmentAgentState)
        graph.add_node("enrich", self._enrich_node)
        graph.add_node("reflect", self._reflect_node)
        graph.add_node("revise", self._revise_node)
        graph.add_edge(START, "enrich")
        graph.add_edge("enrich", "reflect")
        graph.add_conditional_edges(
            "reflect",
            self._reflection_route,
            {"revise": "revise", "final": END},
        )
        graph.add_edge("revise", "reflect")
        return graph.compile()

    def _enrich_node(self, state: EnrichmentAgentState) -> EnrichmentAgentState:
        request = self._require_state_value(state, "request")
        response = self.llm_provider.complete(
            model=self.model,
            messages=self._build_messages(request),
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        payload = self._parse_json(self._extract_content(response))
        return {"enrichment": payload, "attempts": state.get("attempts", 0)}

    def _reflect_node(self, state: EnrichmentAgentState) -> EnrichmentAgentState:
        request = self._require_state_value(state, "request")
        enrichment = self._require_state_value(state, "enrichment")
        response = self.llm_provider.complete(
            model=self.model,
            messages=self._build_reflection_messages(request, enrichment),
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        critique = self._parse_json(self._extract_content(response))
        return {"critique": critique}

    def _revise_node(self, state: EnrichmentAgentState) -> EnrichmentAgentState:
        request = self._require_state_value(state, "request")
        enrichment = self._require_state_value(state, "enrichment")
        critique = self._require_state_value(state, "critique")
        response = self.llm_provider.complete(
            model=self.model,
            messages=self._build_revision_messages(request, enrichment, critique),
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        payload = self._parse_json(self._extract_content(response))
        return {"enrichment": payload, "attempts": state.get("attempts", 0) + 1}

    def _reflection_route(self, state: EnrichmentAgentState) -> Literal["revise", "final"]:
        critique = state.get("critique", {})
        approved = critique.get("approved") if isinstance(critique, dict) else False
        attempts = state.get("attempts", 0)
        if approved is True or attempts >= self.max_reflection_attempts:
            return "final"

        return "revise"

    @overload
    def _require_state_value(
        self,
        state: EnrichmentAgentState,
        key: Literal["request"],
    ) -> EnrichmentRequestSchema: ...

    @overload
    def _require_state_value(
        self,
        state: EnrichmentAgentState,
        key: Literal["enrichment", "critique"],
    ) -> dict[str, object]: ...

    def _require_state_value(
        self,
        state: EnrichmentAgentState,
        key: Literal["request", "enrichment", "critique"],
    ) -> EnrichmentRequestSchema | dict[str, object]:
        value = state.get(key)
        if value is None:
            raise AgentResponseError(f"Enrichment agent state is missing {key!r}.")

        return cast(EnrichmentRequestSchema | dict[str, object], value)

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

    def _build_reflection_messages(
        self,
        request: EnrichmentRequestSchema,
        enrichment: dict[str, object],
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You judge product enrichment quality. Return JSON only with "
                    "keys: approved, issues, revision_instructions. approved must be "
                    "true only when product_code is unchanged, description is improved "
                    "and marketplace-ready, and attributes are supported by the input."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Original product:\n"
                    f"{request.model_dump_json(indent=2)}\n\n"
                    "Candidate enrichment:\n"
                    f"{json.dumps(enrichment, indent=2)}"
                ),
            },
        ]

    def _build_revision_messages(
        self,
        request: EnrichmentRequestSchema,
        enrichment: dict[str, object],
        critique: dict[str, object],
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "Revise product enrichment using the critique. Return JSON only "
                    "with exactly these top-level keys: product_code, description, "
                    "attributes. Keep product_code unchanged and do not invent "
                    "unsupported attributes."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Original product:\n"
                    f"{request.model_dump_json(indent=2)}\n\n"
                    "Candidate enrichment:\n"
                    f"{json.dumps(enrichment, indent=2)}\n\n"
                    "Critique:\n"
                    f"{json.dumps(critique, indent=2)}"
                ),
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
