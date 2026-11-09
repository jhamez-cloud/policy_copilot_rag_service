'''Documentation String'''
from fastapi import APIRouter,Depends,HTTPException
from ...settings import get_settings
from ..schemas import QueryRequest,QueryResponse,SourceOut
from ...rag.pipeline import RagPipeline
from ...rag.generation import GenerationError
from ..dependencies import get_pipeline

router = APIRouter(tags=["Query"])

@router.post("/query",response_model=QueryResponse,summary="Pass ina query or question to be answered by LLM.")
def ask(body:QueryRequest,pipeline:RagPipeline = Depends(get_pipeline)):
    category = body.category.strip() if body.category else None
    try:
        result = pipeline.answer(body.question,body.top_k,category)
    except GenerationError:
        raise HTTPException(503,"The LLM is currently unavailable.")

    return QueryResponse(
        answer = result.text,
        model = get_settings().llm_model,
        sources = [SourceOut(
            document_id=hit.doc_id,
            title=hit.title,
            category=hit.category,
            chunk_id=hit.chunk_id,
            similarity=round(hit.similarity,3),
            excerpt=hit.text[:300]
        ) for hit in result.source]
    )