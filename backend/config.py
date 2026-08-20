from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_env: str = "development"
    competition_mode: bool = True
    database_path: str = "backend/data/app.db"
    knowledge_directory: str = "knowledge"
    llm_provider: str = "openai_compatible"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.2
    llm_timeout: int = 60
    embedding_model: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_timeout: int = 30
    rag_min_score: float = 0.04
    rag_provider: str = "auto"
    xingchen_rag_api_url: str = ""
    xingchen_rag_api_key: str = ""
    xingchen_rag_timeout: int = 20
    xingchen_rag_request_style: str = "workflow"
    xingchen_rag_query_field: str = "query"
    xingchen_rag_context_field: str = "case_context"
    xingchen_rag_user_id: str = "governance-demo"
    xingchen_rag_max_query_chars: int = 200
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_file(self) -> Path:
        path = Path(self.database_path)
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def knowledge_dir(self) -> Path:
        path = Path(self.knowledge_directory)
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def managed_knowledge_dir(self) -> Path:
        return self.database_file.parent / "knowledge"

    @property
    def imports_dir(self) -> Path:
        return self.database_file.parent / "imports"


@lru_cache
def get_settings() -> Settings:
    return Settings()
