import asyncio

import httpx
import pytest

from app.agents.enrichment_agent import EnrichmentAgent
from app.core.config import EnrichmentConfig
from app.dependencies import get_enrichment_service
from app.exceptions import AgentProviderError, AgentResponseError
from app.main import create_app
from app.schemas.enrich import EnrichmentRequestSchema, EnrichmentResponseSchema
from app.services.enrichment_service import EnrichmentService


PAYLOAD = {
    "product_code": "ELEC-001",
    "description": "Wireless Bluetooth Headphones with noise cancellation",
    "attributes": {"brand": "SoundMax", "color": "Black"},
    "instructions": "Make the description more marketplace ready.",
}


def post_json(app, path: str, payload: dict[str, object]) -> httpx.Response:
    async def post() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(path, json=payload)

    return asyncio.run(post())


class FakeAgent:
    def enrich(self, request: EnrichmentRequestSchema) -> EnrichmentResponseSchema:
        return EnrichmentResponseSchema(
            product_code=request.product_code,
            description="SoundMax wireless Bluetooth headphones with active noise cancellation.",
            attributes={**request.attributes, "category": "Headphones"},
        )


class FakeLLMProvider:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[list[dict[str, str]]] = []

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, str] | None = None,
    ) -> dict[str, object]:
        self.calls.append(messages)
        payload = self.responses.pop(0)
        return {"choices": [{"message": {"content": payload["content"]}}]}


def make_agent(
    *,
    model: str = "test/model",
    responses: list[dict[str, object]] | None = None,
    enrichment_config: EnrichmentConfig | None = None,
) -> EnrichmentAgent:
    return EnrichmentAgent(
        model=model,
        llm_provider=FakeLLMProvider(responses or []),
        enrichment_config=enrichment_config,
    )


def test_enrichment_service_delegates_to_agent():
    service = EnrichmentService(agent=FakeAgent())

    response = service.enrich(EnrichmentRequestSchema.model_validate(PAYLOAD))

    assert response.product_code == "ELEC-001"
    assert response.attributes["category"] == "Headphones"


def test_enrich_endpoint_returns_structured_response():
    app = create_app()

    async def get_fake_service() -> EnrichmentService:
        return EnrichmentService(agent=FakeAgent())

    app.dependency_overrides[get_enrichment_service] = get_fake_service

    response = post_json(app, "/enrich", PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {
        "product_code": "ELEC-001",
        "description": "SoundMax wireless Bluetooth headphones with active noise cancellation.",
        "attributes": {
            "brand": "SoundMax",
            "color": "Black",
            "category": "Headphones",
        },
    }


def test_enrich_endpoint_maps_provider_errors_to_bad_gateway():
    class FailingAgent:
        def enrich(self, request: EnrichmentRequestSchema) -> EnrichmentResponseSchema:
            raise AgentProviderError("LLM enrichment request failed.")

    app = create_app()

    async def get_failing_service() -> EnrichmentService:
        return EnrichmentService(agent=FailingAgent())

    app.dependency_overrides[get_enrichment_service] = get_failing_service

    response = post_json(app, "/enrich", PAYLOAD)

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM enrichment request failed."


def test_agent_uses_openai_default_when_only_openai_key_is_configured():
    config = EnrichmentConfig(openai_api_key="test-key", _env_file=None)

    assert config.enrichment_model() == "gpt-4o-mini"


def test_agent_uses_configured_model():
    config = EnrichmentConfig(llm_model="gemini/custom", _env_file=None)

    assert config.enrichment_model() == "gemini/custom"


def test_agent_reports_missing_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    agent = make_agent(
        model="gemini/test",
        enrichment_config=EnrichmentConfig(_env_file=None),
    )

    with pytest.raises(AgentProviderError, match="No Gemini API key configured"):
        agent.enrich(EnrichmentRequestSchema.model_validate(PAYLOAD))


def test_agent_parses_json_fenced_response():
    agent = make_agent(model="gemini/test")
    content = """```json
{"product_code":"HOME-001","description":"Better bottle","attributes":{"capacity":"1L"}}
```"""

    payload = agent._parse_json(content)

    assert payload == {
        "product_code": "HOME-001",
        "description": "Better bottle",
        "attributes": {"capacity": "1L"},
    }


def test_agent_rejects_non_object_json():
    agent = make_agent(model="gemini/test")

    with pytest.raises(AgentResponseError):
        agent._parse_json("[]")


def test_agent_reflects_before_returning_enrichment(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = FakeLLMProvider(
        [
            {
                "content": (
                    '{"product_code":"WRONG","description":"Marketplace ready",'
                    '"attributes":{"brand":"SoundMax"}}'
                )
            },
            {"content": '{"approved":true,"issues":[],"revision_instructions":""}'},
        ]
    )
    agent = EnrichmentAgent(model="test/model", llm_provider=provider)

    response = agent.enrich(EnrichmentRequestSchema.model_validate(PAYLOAD))

    assert response.product_code == "ELEC-001"
    assert response.description == "Marketplace ready"
    assert len(provider.calls) == 2
    assert "judge product enrichment quality" in provider.calls[1][0]["content"]


def test_agent_revises_when_reflection_rejects(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = FakeLLMProvider(
        [
            {
                "content": (
                    '{"product_code":"ELEC-001","description":"Weak",'
                    '"attributes":{"brand":"SoundMax"}}'
                )
            },
            {
                "content": (
                    '{"approved":false,"issues":["description is weak"],'
                    '"revision_instructions":"Make it more marketplace ready."}'
                )
            },
            {
                "content": (
                    '{"product_code":"ELEC-001","description":"SoundMax wireless '
                    'Bluetooth headphones with active noise cancellation.",'
                    '"attributes":{"brand":"SoundMax","color":"Black"}}'
                )
            },
            {"content": '{"approved":true,"issues":[],"revision_instructions":""}'},
        ]
    )
    agent = EnrichmentAgent(model="test/model", llm_provider=provider)

    response = agent.enrich(EnrichmentRequestSchema.model_validate(PAYLOAD))

    assert "active noise cancellation" in response.description
    assert len(provider.calls) == 4
    assert "Revise product enrichment" in provider.calls[2][0]["content"]
