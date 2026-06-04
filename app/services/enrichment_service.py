from __future__ import annotations

import structlog

from app.agents.enrichment_agent import EnrichmentAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.core.logging import logger
from app.exceptions import EnrichmentError
from app.schemas.enrich import EnrichmentRequestSchema, EnrichmentResponseSchema


logger = structlog.get_logger(__name__)


class EnrichmentService:
    def __init__(
        self,
        agent: EnrichmentAgent,
        retrieval_agent: RetrievalAgent | None = None,
    ) -> None:
        self.agent = agent
        self.retrieval_agent = retrieval_agent

    async def enrich(self, request: EnrichmentRequestSchema) -> EnrichmentResponseSchema:
        logger.info(
            "enrichment_service_started"
        )
        if request.file is not None:
            if self.retrieval_agent is None:
                logger.error(
                    "enrichment_service_missing_retrieval_agent",
                    product_code=request.product_code,
                )
                raise EnrichmentError("Retrieval agent is required for PDF enrichment.")

            additional_data_from_files = await self.retrieval_agent.retrieve(request)
            logger.debug(
                "enrichment_service_retrieval_completed"
            )
            request = request.model_copy(
                update={
                    "additional_data_from_files": additional_data_from_files,
                    "file": None,
                },
            )

        response = await self.agent.enrich(request)
        logger.info(
            "enrichment_service_completed",
            product_code=response.product_code,
        )
        return response
