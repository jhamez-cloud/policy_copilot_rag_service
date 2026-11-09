'''Documentation String'''
import re

from fastapi  import Query,Response,Depends,HTTPException,APIRouter,File,Form
from sqlalchemy.orm import Session

from ..dependencies import require_admin,get_pipeline
from ...rag.pipeline import RagPipeline
from ..services import ingestion
from ..db import repository as repo
from ..db.session import get_db
from ..schemas import UploadFileResult,UploadResponse,DocumentDetail,DocumentList,DocumentOut
from ...settings import get_settings


router = APIRouter(prefix="/documents",tags=["Documents"])

CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")


@router.post("/upload",
             response_model=UploadResponse,
             status_code=201,
             dependencies=[Depends(require_admin)],
             summary="Upload one or more files (.md,.markdown,.txt) into the dataset bank."
            )
def upload_document(response:Response,
                    files:list[UploadFileResult] = File(...,description="One or more .md,.markdown or .txt files"),
                    category:str = Form("general",description="Comprised of lower case letters, '_' or '-'"),
                    db:Session = Depends(get_db),
                    pipeline:RagPipeline = Depends(get_pipeline)
                    ):
    settings = get_settings()
    category = category.strip().lower()

    if not CATEGORY_RE.match(category):
        raise HTTPException(422,"category must be 1-50 chars: lowercase letters, digits, '-' or '_'")

    if len(files) > settings.max_files_per_upload:
        raise HTTPException(422,f"At most {settings.max_files_per_upload} file uploads per request")

    results : list[UploadFileResult] = []
    for file in files:
        raw = file.file.read(settings.max_upload_bytes + 1)
        outcome = ingestion.ingest_file(db,pipeline,file.filename)

        results.append(UploadFileResult(
            filename=outcome.filename,
            status=outcome.status,
            detail=outcome.detail,
            document=DocumentOut.model_validate(outcome.document if outcome.document else None)
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
                   db:Session = Depends(get_db)):
    total,rows = repo.get_docs_list(db,category.strip().lower() if category else None,limit,offset)

    return DocumentList(total=total,items=[DocumentOut.model_validate(row) for row in rows])


@router.get("/{doc_id}",response_model=DocumentDetail,summary="Get a single document with full context by its ID.")
def get_document(doc_id:int,db:Session = Depends(get_db)):
    doc = repo.get_doc_by_id(db,doc_id)
    if doc is None:
        raise HTTPException(404,f"Document with ID: {doc_id} Not Found")

    return doc


@router.delete("/{doc_id}",status_code=201,dependencies=[Depends(require_admin)],summary="Remove a document from the dataset bank")
def delete_document(doc_id:int,db:Session = Depends(get_db),pipeline:RagPipeline = Depends(get_pipeline)):
    if not ingestion.delete_document(db,pipeline,doc_id):
        raise HTTPException(404,f"Document with ID: {doc_id} Not Found")

    return Response(status_code=204)