'''API Entry point'''
from fastapi import FastAPI,APIRouter
from fastapi.middleware.cors import CORSMiddleware
from policy_copilot_rag_service.settings import get_settings

root_router = APIRouter(tags=["root"])

@root_router.get("/")
def root():
    return {"status":"Running",
            "message":"If I agree, I\u2019d need to clone myself. And I don't trust him."
            }

def create_app():
    settings = get_settings()
    app = FastAPI(
        title="Policy Copilot RAG Service",
        version="0.1.0",
        description="RAG pipeline for policy copilot entry point",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins = settings.get_cors_orgin_list,
        allow_headers = ["*"],
        allow_methods  = ["*"]
    )

    app.include_router(root_router,prefix="/api/v1")

    # settings._use_psycopg3_driver("postgresql://neondb_owner:npg_amq1shQ5oGlx@ep-dark-field-za8kz1ip-pooler.c-2.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

    return app

app = create_app()

def run() -> None:
    import uvicorn

    uvicorn.run("policy_copilot_rag_service.api.main:app",
                host="127.0.0.1",
                port=8000)

run()