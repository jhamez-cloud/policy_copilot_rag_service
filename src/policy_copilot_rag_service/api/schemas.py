from pydantic import BaseModel,Field,ConfigDict
from datetime import datetime

class QueryRequest(BaseModel):
    question: str = Field(min_length=3,max_length=1000,description="Question prompt entered by user")
    top_k: int | None = Field(default=None,ge=1,le=10,description="Top n chunks to retrieve")
    category: str | None = Field(default=None,description="Limit or narrow down search to document category")


class SourceOut(BaseModel):
    document_id: int
    title: str
    category: str
    chunk_id: str
    similarity: float
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    model: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    filename: str
    source: str
    chunk_count: int
    created_at: datetime


class DocumentDetail(DocumentOut):
    content: str


class DocumentList(BaseModel):
    total: int
    items: list[DocumentOut]


class UploadFileResult(BaseModel):
    filename: str
    status: str
    detail: str = ""
    document: DocumentOut | None


class UploadResponse(BaseModel):
    indexed: int
    skipped: int
    results: list[UploadFileResult]


class HealthOut(BaseModel):
    status: str
    database: bool
    documents: int
    indexed_chunks: int 