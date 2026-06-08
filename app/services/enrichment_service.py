from __future__ import annotations

import structlog
from opentelemetry import trace


from app.agents.enrichment_agent import EnrichmentAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.core.logging import logger
from app.exceptions import EnrichmentError
from app.schemas.enrich import EnrichmentRequestSchema, EnrichmentResponseSchema


tracer = trace.get_tracer(__name__)
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
        # Child span: the overall business transaction
        with tracer.start_as_current_span("enrichment_service.enrich") as span:
            span.set_attribute("product_code", request.product_code)
            span.set_attribute("has_file", request.file is not None)

            logger.info("enrichment_service_started")

            if request.file is not None:
                if self.retrieval_agent is None:
                    logger.error(
                        "enrichment_service_missing_retrieval_agent",
                        product_code=request.product_code,
                    )
                    raise EnrichmentError("Retrieval agent is required for PDF enrichment.")

                # Nested child span: file retrieval
                with tracer.start_as_current_span("enrichment_service.retrieval") as retrieval_span:
                    retrieval_span.set_attribute("file_name", request.file.filename if hasattr(request.file, "filename") else "unknown")
                    
                    additional_data_from_files = await self.retrieval_agent.retrieve(request)
                    
                    retrieval_span.set_attribute("retrieval_success", True)
                    logger.debug("enrichment_service_retrieval_completed")

                request = request.model_copy(
                    update={
                        "additional_data_from_files": additional_data_from_files,
                        "file": None,
                    },
                )

            # Nested child span: LLM/agent enrichment
            with tracer.start_as_current_span("enrichment_service.agent_enrich") as agent_span:
                agent_span.set_attribute("product_code", request.product_code)
                
                response = await self.agent.enrich(request)
                
                agent_span.set_attribute("response_product_code", response.product_code)

            span.set_attribute("response_product_code", response.product_code)
            logger.info("enrichment_service_completed", product_code=response.product_code)
            return response