from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

class QueryRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)] = Field(description="Question prompt entered by user")
    top_k: int | None = Field(default=None,ge=1,le=10,description="Maximum chunks per corpus: selected library and software policies")
    category: str | None = Field(default=None,description="Filter uploaded documents by category; software policies are searched across all categories")
    session_id: int | None = Field(default=None, ge=1, description="Session whose selected library is searched; omit to search uncategorized documents")


class SourceOut(BaseModel):
    document_id: int
    title: str
    category: str
    chunk_id: str
    similarity: float
    excerpt: str
    source: str = "upload"


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    model: str
    session_id: int | None = None
    library_id: int | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    filename: str
    source: str
    chunk_count: int
    created_at: datetime
    library_id: int | None = None


class DocumentDetail(DocumentOut):
    content: str = Field(description="Normalized readable text extracted from the original document; used for indexing")


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


class UploadOptions(BaseModel):
    supported_extensions: list[str]
    max_upload_bytes: int
    max_files_per_upload: int
    max_extracted_chars: int


LibraryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
DocumentId = Annotated[int, Field(ge=1)]


class LibraryCreate(BaseModel):
    name: LibraryName


class LibraryRename(LibraryCreate):
    pass


class LibraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    is_system: bool


class LibraryList(BaseModel):
    total: int
    items: list[LibraryOut]


class LibraryDocumentsRequest(BaseModel):
    document_ids: list[DocumentId] = Field(min_length=1, max_length=1000)

    @field_validator("document_ids")
    @classmethod
    def unique_document_ids(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise ValueError("document_ids must not contain duplicates")
        return values


class SessionCreate(BaseModel):
    library_id: int = Field(ge=1)


class SessionUpdate(SessionCreate):
    pass


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    library_id: int | None
    created_at: datetime


class SessionList(BaseModel):
    total: int
    items: list[SessionOut]


class HealthOut(BaseModel):
    status: str
    database: bool
    documents: int
    indexed_chunks: int
