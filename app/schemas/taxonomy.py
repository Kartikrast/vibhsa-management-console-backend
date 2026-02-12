from pydantic import BaseModel
from uuid import UUID


class SimpleTaxonomyResponse(BaseModel):
    id: UUID
    name: str
    short_code: str

    class Config:
        from_attributes = True
