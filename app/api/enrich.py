import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.exceptions import AgentProviderError, AgentResponseError, EnrichmentError
from app.schemas.enrich import EnrichmentRequestSchema, EnrichmentResponseSchema
from app.services.enrichment_service import EnrichmentService


router = APIRouter()
logger = structlog.get_logger(__name__)


async def get_enrichment_service() -> EnrichmentService:
    return EnrichmentService()


@router.post("/enrich", response_model=EnrichmentResponseSchema)
async def enrich_product(
    request: EnrichmentRequestSchema,
    service: EnrichmentService = Depends(get_enrichment_service),
) -> EnrichmentResponseSchema:
    try:
        return service.enrich(request)
    except AgentProviderError as exc:
        logger.warning(
            "enrichment_provider_failed",
            product_code=request.product_code,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except AgentResponseError as exc:
        logger.warning("enrichment_response_invalid", product_code=request.product_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except EnrichmentError as exc:
        logger.exception("enrichment_failed", product_code=request.product_code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Product enrichment failed.",
        ) from exc
