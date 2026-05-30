from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


# Request
class EnrichmentRequestSchema(BaseModel):
    product_code: str = Field(..., min_length=2)
    description: str = Field(..., min_length=2)
    attributes: Dict[str, Any] = Field(...)
    instructions: Optional[str] = Field(...)


# Response
class EnrichmentResponseSchema(BaseModel):
    product_code: str = Field(..., min_length=2)
    description: str = Field(..., min_length=2)
    attributes: Dict[str, Any] = Field(...)
