from pydantic import BaseModel
from typing import List, Optional


class BulkUploadError(BaseModel):
    row: int
    error: str


class BulkUploadResponse(BaseModel):
    total_rows: int
    created: int
    failed: int
    errors: List[BulkUploadError]
