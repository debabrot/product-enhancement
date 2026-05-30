import asyncio

import httpx
import pytest

from app.agents.enrichment_agent import EnrichmentAgent
from app.api.enrich import get_enrichment_service
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


def test_agent_uses_openai_default_when_only_openai_key_is_configured(monkeypatch):
    monkeypatch.delenv("ENRICHMENT_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    agent = EnrichmentAgent()

    assert agent.model == "gpt-4o-mini"


def test_agent_uses_configured_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gemini/custom")

    agent = EnrichmentAgent()

    assert agent.model == "gemini/custom"


def test_agent_reports_missing_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    agent = EnrichmentAgent(model="gemini/test")

    with pytest.raises(AgentProviderError, match="No Gemini API key configured"):
        agent.enrich(EnrichmentRequestSchema.model_validate(PAYLOAD))


def test_agent_parses_json_fenced_response():
    agent = EnrichmentAgent(model="gemini/test")
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
    agent = EnrichmentAgent(model="gemini/test")

    with pytest.raises(AgentResponseError):
        agent._parse_json("[]")
