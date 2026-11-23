'''API Entry point'''
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware

from policy_copilot_rag_service.settings import get_settings
from .routes import health,query,document,library,session
from .db.session import init_db,get_session_factory,dispose_engine
from .db.repository import SystemLibraryError
from ..rag.pipeline import RagPipeline
from ..rag.embeddings import get_embedding_model
from .services import ingestion

logger = logging.getLogger("policy_rag")

root_router = APIRouter(tags=["root"])


@root_router.get("/")
def root():
    return {
        "status": "Running",
        "message": "If I agree, I\u2019d need to clone myself. And I don't trust him.",
    }


@asynccontextmanager
async def lifespan(app:FastAPI):
    '''App Lifecycle'''

    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    init_db()
    pipeline = RagPipeline()

    with get_session_factory()() as db:
        if settings.seed_on_startup:
            seeded =  ingestion.seed_from_directory(db,settings.data_dir)
            logger.info("Seeded %d new documents from %s", seeded, str(settings.data_dir))

    get_embedding_model()

    with get_session_factory()() as db:
        docs,chunks = ingestion.rebuild_index(pipeline,db)

    logger.info("Vector Index Ready: %d documents , %d chunks",docs,chunks)

    app.state.pipeline = pipeline

    yield

    dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Policy Copilot RAG Service",
        version="0.1.0",
        description="RAG pipeline for policy copilot entry point",
        lifespan=lifespan
    )
    app.openapi_version = "3.0.3"

    @app.exception_handler(SystemLibraryError)
    async def protected_policy_error(_request: Request, error: SystemLibraryError):
        return JSONResponse(status_code=403, content={"detail": str(error)})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_orgin_list,
        allow_headers=["*"],
        allow_methods=["*"],
    )

    app.include_router(root_router, prefix="/api/v1")
    app.include_router(health.router)
    app.include_router(query.router,prefix="/api/v1")
    app.include_router(document.router,prefix="/api/v1")
    app.include_router(library.router,prefix="/api/v1")
    app.include_router(session.router,prefix="/api/v1")

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            openapi_version="3.0.3",
        )
        upload_operation = schema["paths"]["/api/v1/documents/upload"]["post"]
        request_schema_ref = upload_operation["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"]
        request_schema_name = request_schema_ref.rsplit("/", 1)[-1]
        files_item_schema = schema["components"]["schemas"][request_schema_name]["properties"]["files"]["items"]
        files_item_schema.pop("contentMediaType", None)
        files_item_schema["format"] = "binary"

        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi
    return app


app = create_app()


def run() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Run the Policy Copilot RAG API")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--reload", action="store_true", help="Enable development reload")
    args = parser.parse_args()

    uvicorn.run(
        "policy_copilot_rag_service.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    run()
