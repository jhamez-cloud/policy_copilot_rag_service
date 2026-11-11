"""Library management and document membership."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..db import repository as repo
from ..db.models import Document, Library
from ..db.session import get_db
from ..dependencies import require_admin
from ..schemas import (
    DocumentList,
    DocumentOut,
    LibraryCreate,
    LibraryDocumentsRequest,
    LibraryList,
    LibraryOut,
    LibraryRename,
)

router = APIRouter(prefix="/libraries", tags=["Libraries"])


def _get_library(db: Session, library_id: int) -> Library:
    library = repo.get_library_by_id(db, library_id)
    if library is None:
        raise HTTPException(404, f"Library with ID: {library_id} Not Found")
    return library


def _get_documents(db: Session, document_ids: list[int]) -> list[Document]:
    documents = repo.get_docs_by_ids(db, document_ids)
    by_id = {document.id: document for document in documents}
    missing = [document_id for document_id in document_ids if document_id not in by_id]
    if missing:
        raise HTTPException(404, {"message": "Documents not found", "document_ids": missing})
    return [by_id[document_id] for document_id in document_ids]


@router.post("", response_model=LibraryOut, status_code=201, dependencies=[Depends(require_admin)])
def create_library(body: LibraryCreate, db: Session = Depends(get_db)):
    library = repo.add_library(db, name=body.name)
    db.commit()
    return library


@router.get("", response_model=LibraryList)
def list_libraries(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total, libraries = repo.get_libraries_list(db, limit, offset)
    return LibraryList(total=total, items=[LibraryOut.model_validate(library) for library in libraries])


@router.get("/{library_id}", response_model=LibraryOut)
def get_library(library_id: int, db: Session = Depends(get_db)):
    return _get_library(db, library_id)


@router.patch("/{library_id}", response_model=LibraryOut, dependencies=[Depends(require_admin)])
def rename_library(library_id: int, body: LibraryRename, db: Session = Depends(get_db)):
    library = _get_library(db, library_id)
    repo.require_mutable_library(library)
    library.name = body.name
    db.commit()
    return library


@router.delete("/{library_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_library(library_id: int, db: Session = Depends(get_db)):
    library = _get_library(db, library_id)
    repo.delete_library(db, library)
    db.commit()
    return Response(status_code=204)


@router.get("/{library_id}/documents", response_model=DocumentList)
def list_library_documents(
    library_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: str | None = None,
    db: Session = Depends(get_db),
):
    _get_library(db, library_id)
    total, documents = repo.get_docs_list(
        db, category.strip().lower() if category else None, limit, offset, library_id=library_id
    )
    return DocumentList(total=total, items=[DocumentOut.model_validate(document) for document in documents])


@router.post("/{library_id}/documents", response_model=DocumentList, dependencies=[Depends(require_admin)])
def add_documents(library_id: int, body: LibraryDocumentsRequest, db: Session = Depends(get_db)):
    """Move the requested documents into this library in one transaction."""
    repo.require_mutable_library(_get_library(db, library_id))
    documents = _get_documents(db, body.document_ids)
    repo.assign_documents_to_library(db, library_id, documents)
    db.commit()
    return DocumentList(total=len(documents), items=[DocumentOut.model_validate(document) for document in documents])


@router.delete("/{library_id}/documents", response_model=DocumentList, dependencies=[Depends(require_admin)])
def remove_documents(library_id: int, body: LibraryDocumentsRequest, db: Session = Depends(get_db)):
    """Keep the requested documents and mark their library membership as uncategorized."""
    repo.require_mutable_library(_get_library(db, library_id))
    documents = _get_documents(db, body.document_ids)
    outside_library = [document.id for document in documents if document.library_id != library_id]
    if outside_library:
        raise HTTPException(404, {"message": "Documents are not in this library", "document_ids": outside_library})
    repo.remove_documents_from_library(db, library_id, documents)
    db.commit()
    return DocumentList(total=len(documents), items=[DocumentOut.model_validate(document) for document in documents])


@router.delete("/{library_id}/documents/{doc_id}", status_code=204, dependencies=[Depends(require_admin)])
def remove_document(library_id: int, doc_id: int, db: Session = Depends(get_db)):
    repo.require_mutable_library(_get_library(db, library_id))
    documents = _get_documents(db, [doc_id])
    if documents[0].library_id != library_id:
        raise HTTPException(404, f"Document with ID: {doc_id} is not in this library")
    repo.remove_documents_from_library(db, library_id, documents)
    db.commit()
    return Response(status_code=204)
