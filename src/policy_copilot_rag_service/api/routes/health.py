from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Response,Depends,APIRouter

from ...api.schemas import HealthOut
from ...rag.pipeline import RagPipeline
from ..dependencies import get_pipeline
from ..db.session import get_db
from ..db import repository as repo


router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthOut)
def Health(response:Response,db:Session = Depends(get_db),pipeline:RagPipeline = Depends(get_pipeline)):
    try:
        db.execute(text("SELECT 1"))
        documents,database_ok = repo.get_doc_count(db),True
    except Exception:
        documents,database_ok = 0,False
        response.status_code = 503
    return HealthOut(
        status = "ok" if database_ok else "degraded",
        database = database_ok,
        documents = documents,
        indexed_chunks = pipeline.vector_db.count()
    )
