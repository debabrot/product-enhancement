from app.agents.enrichment_agent import EnrichmentAgent
from app.schemas.enrich import EnrichmentRequestSchema, EnrichmentResponseSchema


class EnrichmentService:
    def __init__(
        self,
        agent: EnrichmentAgent,
    ) -> None:
        self.agent = agent

    def enrich(self, request: EnrichmentRequestSchema) -> EnrichmentResponseSchema:
        return self.agent.enrich(request)
