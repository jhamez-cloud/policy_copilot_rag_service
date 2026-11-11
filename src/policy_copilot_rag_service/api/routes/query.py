'''Documentation String'''
from fastapi import APIRouter,Depends,HTTPException
from ...settings import get_settings
from ..schemas import QueryRequest,QueryResponse,SourceOut
from ...rag.pipeline import RagPipeline
from ...rag.generation import GenerationError,GenerationTimeout
from ..dependencies import get_pipeline
from ..db import repository as repo
from ..db.session import get_db
from sqlalchemy.orm import Session

router = APIRouter(tags=["Query"])

@router.post("/query",response_model=QueryResponse,summary="Pass ina query or question to be answered by LLM.")
def ask(body:QueryRequest,pipeline:RagPipeline = Depends(get_pipeline),db:Session = Depends(get_db)):
    category = body.category.strip().lower() if body.category else None
    library_id = None
    if body.session_id is not None:
        session = repo.get_chat_session_by_id(db, body.session_id)
        if session is None:
            raise HTTPException(404, f"Session with ID: {body.session_id} Not Found")
        library_id = session.library_id
        # A deleted library must not turn a session into a search over unrelated uploads.
        document_ids = repo.get_document_ids_for_library(db, library_id) if library_id is not None else []
    else:
        document_ids = repo.get_document_ids_for_library(db, None)
    policy_document_ids = repo.get_policy_document_ids(db)
    try:
        result = pipeline.answer(
            body.question, body.top_k, category,
            document_ids=document_ids, policy_document_ids=policy_document_ids,
        )
    except GenerationTimeout as err:
        raise HTTPException(504,err.detail) from err
    except GenerationError as err:
        raise HTTPException(503,err.detail) from err

    return QueryResponse(
        answer = result.text,
        model = get_settings().llm_model,
        session_id = body.session_id,
        library_id = library_id,
        sources = [SourceOut(
            document_id=hit.doc_id,
            title=hit.title,
            category=hit.category,
            chunk_id=hit.chunk_id,
            similarity=round(hit.similarity,3),
            excerpt=hit.text[:300],
            source=hit.source,
        ) for hit in result.source]
    )
