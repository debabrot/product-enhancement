from fastapi import Depends

from app.agents.enrichment_agent import EnrichmentAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.core.config import Config
from app.llm.provider import LLMProvider, LLMProviderProtocol
from app.services.enrichment_service import EnrichmentService


async def get_enrichment_config() -> Config:
    return Config()


async def get_gemini_llm_provider(
    config: Config = Depends(get_enrichment_config),
) -> LLMProviderProtocol:
    return LLMProvider(
        model=config.gemini_model)


async def get_openrouter_llm_provider(
    config: Config = Depends(get_enrichment_config),
) -> LLMProvider:
    return LLMProvider(
        model=config.openrouter_llm_model
)


async def get_enrichment_agent(
    config: Config = Depends(get_enrichment_config),
    llm_provider: LLMProvider = Depends(get_openrouter_llm_provider),
) -> EnrichmentAgent:
    return EnrichmentAgent(
        llm_provider=llm_provider,
        config=config,
    )


async def get_retrieval_agent(
    config: Config = Depends(get_enrichment_config),
    llm_provider: LLMProvider = Depends(get_openrouter_llm_provider),
) -> RetrievalAgent:
    return RetrievalAgent(
        llm_provider=llm_provider,
        config=config,
    )


async def get_enrichment_service(
    agent: EnrichmentAgent = Depends(get_enrichment_agent),
    retrieval_agent: RetrievalAgent = Depends(get_retrieval_agent),
) -> EnrichmentService:
    return EnrichmentService(agent=agent, retrieval_agent=retrieval_agent)
