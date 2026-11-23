'''Documentation String'''
import secrets
from fastapi import Header,HTTPException,Request,status
from ..settings import get_settings
from ..rag.pipeline import RagPipeline

def get_pipeline(request:Request) -> RagPipeline:
    return request.app.state.pipeline

def require_admin(x_api_key:str | None = Header(default=None, alias="X-API-Key")):
    expected = get_settings().admin_api_key

    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Admin-API-Key Not Configured, Service May Not Be Available Yet.")

    if not x_api_key or not secrets.compare_digest(x_api_key.encode(),expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Unauthorized!, Invalid or Missing API Key.")