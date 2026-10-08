from pydantic import BaseModel, ConfigDict, Field


class SourceCreate(BaseModel):
    name: str
    kind: str = "sqlite"
    url: str


class SourceOut(SourceCreate):
    id: int
    enabled: bool
    model_config = ConfigDict(from_attributes=True)


class SemanticResult(BaseModel):
    business_name: str
    description: str
    semantic_type: str = "其他"
    sensitivity: str = "L1-公开"
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = []


class ReviewRequest(BaseModel):
    business_name: str | None = None
    description: str | None = None
    domain: str | None = None
    status: str = "approved"


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(10, ge=1, le=50)
