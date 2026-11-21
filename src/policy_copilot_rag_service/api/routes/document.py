'''Documentation String'''
import re

from typing import Annotated
from fastapi  import Query,Response,Depends,HTTPException,APIRouter,File,Form,UploadFile
from sqlalchemy.orm import Session

from ..dependencies import require_admin,get_pipeline
from ...rag.pipeline import RagPipeline
from ..services import ingestion
from ..services.extraction import available_extensions
from ..db import repository as repo
from ..db.session import get_db
from ..schemas import UploadFileResult,UploadResponse,UploadOptions,DocumentDetail,DocumentList,DocumentOut
from ...settings import get_settings


router = APIRouter(prefix="/documents",tags=["Documents"])

CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")


@router.get("/upload-options", response_model=UploadOptions, summary="Get available upload formats and configured limits")
def upload_options():
    settings = get_settings()
    return UploadOptions(
        supported_extensions=available_extensions(),
        max_upload_bytes=settings.max_upload_bytes,
        max_files_per_upload=settings.max_files_per_upload,
        max_extracted_chars=settings.max_extracted_chars,
    )


@router.post("/upload",
             response_model=UploadResponse,
             status_code=201,
             dependencies=[Depends(require_admin)],
             summary="Upload and index PDF, Word, PowerPoint, CSV, text or Markdown documents",
             description="Extracts readable text from .pdf, .docx, .doc, .pptx, .ppt, .csv, .txt, .md and .markdown files. Legacy .doc uses antiword with a LibreOffice fallback; legacy .ppt requires LibreOffice. Scanned or image-only documents require OCR before upload. Password-protected files are rejected individually."
            )
def upload_document(response:Response,
                    files:Annotated[list[UploadFile], File(...,description="One or more .pdf, .docx, .doc, .pptx, .ppt, .csv, .txt, .md or .markdown files")],
                    category:Annotated[str, Form(description="Comprised of lower case letters, '_' or '-'") ] = "general",
                    library_id:Annotated[int | None, Form(ge=1,description="Selected library; omit to leave uploads uncategorized")] = None,
                    db:Session = Depends(get_db),
                    pipeline:RagPipeline = Depends(get_pipeline)
                    ):
    settings = get_settings()
    category = category.strip().lower()

    if not CATEGORY_RE.match(category):
        raise HTTPException(422,"category must be 1-50 chars: lowercase letters, digits, '-' or '_'")

    if len(files) > settings.max_files_per_upload:
        raise HTTPException(422,f"At most {settings.max_files_per_upload} file uploads per request")

    if library_id is not None:
        library = repo.get_library_by_id(db, library_id)
        if library is None:
            raise HTTPException(404,f"Library with ID: {library_id} Not Found")
        repo.require_mutable_library(library)

    results : list[UploadFileResult] = []
    for file in files:
        raw = file.file.read(settings.max_upload_bytes + 1)
        outcome = ingestion.ingest_file(db,pipeline,file.filename or "upload",raw,category,library_id=library_id)

        results.append(UploadFileResult(
            filename=outcome.filename,
            status=outcome.status,
            detail=outcome.detail,
            document=DocumentOut.model_validate(outcome.document) if outcome.document is not None else None,
        ))

    indexed = sum(result.status == "indexed" for result in results)
    skipped = len(results) - indexed

    if indexed == 0:
        response.status_code = 200

    return UploadResponse(indexed=indexed,skipped=skipped,results=results)


@router.get("",response_model=DocumentList,summary="Get a list of all documents")
def list_documents(limit:int = Query(20, ge=1, le=100),
                   offset:int = Query(0, ge=0),
                   category:str | None = None,
                   library_id:int | None = Query(None,ge=1),
                   uncategorized:bool = False,
                   db:Session = Depends(get_db)):
    if library_id is not None and uncategorized:
        raise HTTPException(422,"Choose either library_id or uncategorized")
    if library_id is not None and repo.get_library_by_id(db, library_id) is None:
        raise HTTPException(404,f"Library with ID: {library_id} Not Found")
    total,rows = repo.get_docs_list(
        db,category.strip().lower() if category else None,limit,offset,
        library_id=library_id,uncategorized=uncategorized,
    )

    return DocumentList(total=total,items=[DocumentOut.model_validate(row) for row in rows])


@router.get("/{doc_id}",response_model=DocumentDetail,summary="Get a single document with full context by its ID.")
def get_document(doc_id:int,db:Session = Depends(get_db)):
    doc = repo.get_doc_by_id(db,doc_id)
    if doc is None:
        raise HTTPException(404,f"Document with ID: {doc_id} Not Found")

    return doc


@router.delete("/{doc_id}",status_code=204,dependencies=[Depends(require_admin)],summary="Remove a document from the dataset bank")
def delete_document(doc_id:int,db:Session = Depends(get_db),pipeline:RagPipeline = Depends(get_pipeline)):
    if not ingestion.delete_document(db,pipeline,doc_id):
        raise HTTPException(404,f"Document with ID: {doc_id} Not Found")

    return Response(status_code=204)
