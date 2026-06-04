from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import UploadFile


# Request
class EnrichmentRequestSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    product_code: str = Field(..., min_length=2)
    description: str = Field(..., min_length=2)
    attributes: Dict[str, Any] = Field(...)
    instructions: Optional[str] = Field(...)
    file: Optional[UploadFile] = Field(default=None, exclude=True)
    additional_data_from_files: Optional[str] = Field(default=None)


# Response
class EnrichmentResponseSchema(BaseModel):
    product_code: str = Field(..., min_length=2)
    description: str = Field(..., min_length=2)
    attributes: Dict[str, Any] = Field(...)
