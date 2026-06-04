from __future__ import annotations

import json
import asyncio
from collections.abc import Mapping
from io import BytesIO
from typing import Literal, TypedDict, cast, overload

import pdfplumber
import structlog
from langgraph.graph import END, START, StateGraph

from app.core.config import Config
from app.exceptions import AgentProviderError, AgentResponseError
from app.llm.provider import LLMProvider
from app.schemas.enrich import EnrichmentRequestSchema


MAX_PDF_CONTEXT_CHARS = 30_000
logger = structlog.get_logger(__name__)


class RetrievalAgentState(TypedDict, total=False):
    request: EnrichmentRequestSchema
    extracted_text: str
    relevant_text: str


class RetrievalAgent:
    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        config: Config | None = None,
        max_pdf_context_chars: int = MAX_PDF_CONTEXT_CHARS,
    ) -> None:
        self.llm_provider = llm_provider
        self.config = config
        self.max_pdf_context_chars = max_pdf_context_chars
        self._graph = self._build_graph()

    async def retrieve(self, request: EnrichmentRequestSchema) -> str:
        if request.file is None:
            logger.debug(
                "retrieval_agent_skipped",
                reason="missing_file",
            )
            return ""

        logger.info(
            "retrieval_agent_started",
            has_file=True,
            filename=request.file.filename,
            content_type=request.file.content_type,
        )
        try:
            final_state = await self._graph.ainvoke({"request": request})
        except Exception as exc:
            if isinstance(exc, AgentResponseError):
                raise exc
            raise AgentProviderError(
                f"LLM retrieval request failed : {exc}"
            ) from exc

        relevant_text = final_state.get("relevant_text")
        if not isinstance(relevant_text, str):
            raise AgentResponseError("Retrieval agent did not produce text output.")

        logger.info(
            "retrieval_agent_completed",
            relevant_text_chars=len(relevant_text),
            relevant_text_preview=relevant_text[:120] if relevant_text else "",
        )
        return relevant_text.strip()

    def _build_graph(self):
        graph = StateGraph(RetrievalAgentState)
        graph.add_node("extract_pdf_text", self._extract_pdf_text_node)
        graph.add_node("select_relevant_text", self._select_relevant_text_node)
        graph.add_edge(START, "extract_pdf_text")
        graph.add_edge("extract_pdf_text", "select_relevant_text")
        graph.add_edge("select_relevant_text", END)
        return graph.compile()

    async def _extract_pdf_text_node(
        self,
        state: RetrievalAgentState,
    ) -> RetrievalAgentState:
        request = self._require_state_value(state, "request")
        file = request.file
        if file is None:
            logger.debug("retrieval_agent_extract_skipped", reason="missing_file")
            return {"extracted_text": ""}

        logger.debug(
            "retrieval_agent_extract_started",
            filename=file.filename,
            content_type=file.content_type,
        )

        def _read_pdf() -> tuple[list[str], int]:
            stream = file.file
            try:
                stream.seek(0)
                pdf_bytes = BytesIO(stream.read())
                with pdfplumber.open(pdf_bytes) as pdf:
                    total_pages = len(pdf.pages)
                    pages = [
                        page_text.strip()
                        for page in pdf.pages
                        if (page_text := page.extract_text())
                    ]
                return pages, total_pages
            except Exception as exc:
                raise AgentResponseError("Could not extract text from uploaded PDF.") from exc
            finally:
                stream.seek(0)

        pages, total_pages = await asyncio.to_thread(_read_pdf)
        extracted_text = "\n\n".join(pages)

        logger.debug(
            "retrieval_agent_extract_completed",
            total_pages=total_pages,
            pages_with_text=len(pages),
            extracted_chars=len(extracted_text),
            truncated=len(extracted_text) > self.max_pdf_context_chars,
        )
        return {"extracted_text": extracted_text}

    async def _select_relevant_text_node(
        self,
        state: RetrievalAgentState,
    ) -> RetrievalAgentState:
        request = self._require_state_value(state, "request")
        extracted_text = self._require_state_value(state, "extracted_text")
        if not extracted_text.strip():
            logger.debug("retrieval_agent_selection_skipped", reason="empty_pdf_text")
            return {"relevant_text": ""}

        messages = self._build_messages(request, extracted_text)
        logger.debug(
            "retrieval_agent_llm_request",
            message_count=len(messages),
            roles=[m["role"] for m in messages],
            user_content_chars=len(messages[-1]["content"]) if messages else 0,
        )
        response = await self.llm_provider.complete(
            messages=messages,
            response_format={"type": "json_object"},
        )
        content = self._extract_content(response)
        logger.debug(
            "retrieval_agent_llm_response",
            response_chars=len(content),
            response_preview=content[:120],
        )
        payload = self._parse_json(content)
        logger.debug(
            "retrieval_agent_parsed_response",
            payload_keys=list(payload.keys()),
        )
        relevant_text = payload.get("relevant_text")
        if not isinstance(relevant_text, str):
            raise AgentResponseError("Retrieval agent JSON must include relevant_text.")

        return {"relevant_text": relevant_text}

    @overload
    def _require_state_value(
        self,
        state: RetrievalAgentState,
        key: Literal["request"],
    ) -> EnrichmentRequestSchema: ...

    @overload
    def _require_state_value(
        self,
        state: RetrievalAgentState,
        key: Literal["extracted_text", "relevant_text"],
    ) -> str: ...

    def _require_state_value(
        self,
        state: RetrievalAgentState,
        key: Literal["request", "extracted_text", "relevant_text"],
    ) -> EnrichmentRequestSchema | str:
        value = state.get(key)
        if value is None:
            raise AgentResponseError(f"Retrieval agent state is missing {key!r}.")

        return cast(EnrichmentRequestSchema | str, value)

    def _build_messages(
        self,
        request: EnrichmentRequestSchema,
        extracted_text: str,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You extract relevant product context from PDF text. Return JSON "
                    "only with exactly one key: relevant_text. Include only facts from "
                    "the PDF that are relevant to the product description, attributes, "
                    "and user instructions. Do not invent, infer, or include boilerplate."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Product request:\n"
                    f"{self._request_prompt_json(request)}\n\n"
                    "Extracted PDF text:\n"
                    f"{self._trim_pdf_text(extracted_text)}"
                ),
            },
        ]

    def _trim_pdf_text(self, extracted_text: str) -> str:
        if len(extracted_text) <= self.max_pdf_context_chars:
            return extracted_text

        return extracted_text[: self.max_pdf_context_chars]

    def _request_prompt_json(self, request: EnrichmentRequestSchema) -> str:
        payload = request.model_dump(exclude={"file", "additional_data_from_files"})
        return json.dumps(payload, indent=2)

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