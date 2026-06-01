from fastapi import Depends

from app.agents.enrichment_agent import EnrichmentAgent
from app.core.config import EnrichmentConfig
from app.llm.provider import LLMProvider, LiteLLMProvider
from app.services.enrichment_service import EnrichmentService


async def get_enrichment_config() -> EnrichmentConfig:
    return EnrichmentConfig()


async def get_llm_provider() -> LLMProvider:
    return LiteLLMProvider()


async def get_enrichment_agent(
    config: EnrichmentConfig = Depends(get_enrichment_config),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> EnrichmentAgent:
    return EnrichmentAgent(
        model=config.enrichment_model(),
        llm_provider=llm_provider,
        enrichment_config=config,
    )


async def get_enrichment_service(
    agent: EnrichmentAgent = Depends(get_enrichment_agent),
) -> EnrichmentService:
    return EnrichmentService(agent=agent)
