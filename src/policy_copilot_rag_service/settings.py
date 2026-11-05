'''Documentation String'''
from pathlib import Path
from pydantic_settings import BaseSettings,SettingsConfigDict
from functools import lru_cache
from pydantic import field_validator
from typing import List

BASE_DIR = Path(__file__).resolve().parents[2]
# print(BASE_DIR)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    database_url:str = "postgresql://neondb_owner:npg_amq1shQ5oGlx@ep-dark-field-za8kz1ip-pooler.c-2.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

    admin_api_key: str = ""
    cors_allowed_origins: str = "http://localhost:3000"
    max_upload_bytes: int = 1000000
    max_files_per_upload:  int = 10
    log_level: str = "INFO"

    data_dir: Path = BASE_DIR / "data" / "policies"
    seed_on_startup: bool = True

    chunk_size: int = 400
    chunk_overlap: int = 100

    embedding_model: str = "all-MiniLm-L6-v2"
    collection_name: str = "policy_documents"
    similarity_metric: str = "cosine"

    top_k: int = 3
    max_top_k: int = 6
    min_similarity: float = 0.0

    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_model: str = "gemini-2.5-flash"
    llm_api_key: str = ""
    llm_max_tokens: int = 1000
    llm_timeout_seconds: float = 30.0

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3_driver(cls,db_url: str):
        if db_url.startswith("postgres://"):
            db_url = "postgresql" + db_url[len("postgres://"):]
        if db_url.startswith("postgresql://"):
            db_url = "postgresql+psycopg://" + db_url[len("postgresql://"):]

        print(db_url)

        return db_url

    @property
    def get_cors_orgin_list(self) -> List[str]:
        return [allowed_origin.strip() for allowed_origin in self.cors_allowed_origins.split(",") if allowed_origin.strip()]



@lru_cache
def get_settings() -> Settings:
    return Settings()