import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.dependencies import get_enrichment_service
from app.exceptions import AgentProviderError, AgentResponseError, EnrichmentError
from app.schemas.enrich import EnrichmentRequestSchema, EnrichmentResponseSchema
from app.services.enrichment_service import EnrichmentService


router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/enrich", response_model=EnrichmentResponseSchema)
async def enrich_product(
    raw_request: Request,
    service: EnrichmentService = Depends(get_enrichment_service),
) -> EnrichmentResponseSchema:
    request = await _parse_enrichment_request(raw_request)
    try:
        response = await service.enrich(request)
        logger.info(
            "route_service_returned",
            product_code=response.product_code,
            response=response.model_dump()
        )
        return response
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


async def _parse_enrichment_request(raw_request: Request) -> EnrichmentRequestSchema:
    content_type = raw_request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await raw_request.form()
        payload = form.get("payload")
        if not isinstance(payload, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Multipart enrich requests must include a JSON payload field.",
            )

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Multipart payload field must contain valid JSON.",
            ) from exc

        file = form.get("file")
        if file is not None:
            if not isinstance(file, UploadFile):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Multipart file field must be an uploaded PDF file.",
                )
            if not _is_pdf_file(file):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Multipart file field must be a PDF file.",
                )
            data["file"] = file

        return _validate_enrichment_data(data)

    try:
        data = await raw_request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request body must contain valid JSON.",
        ) from exc

    return _validate_enrichment_data(data)


def _is_pdf_file(file: UploadFile) -> bool:
    filename = file.filename or ""
    return file.content_type == "application/pdf" or filename.lower().endswith(".pdf")


def _validate_enrichment_data(data: object) -> EnrichmentRequestSchema:
    try:
        return EnrichmentRequestSchema.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc
