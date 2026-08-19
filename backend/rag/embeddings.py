from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from config import get_settings


def embedding_configured() -> bool:
    settings = get_settings()
    return bool(settings.embedding_model and settings.embedding_api_key)


def get_embedding_model() -> OpenAIEmbeddings | None:
    settings = get_settings()
    if not embedding_configured():
        return None
    kwargs = {
        "model": settings.embedding_model,
        "api_key": settings.embedding_api_key,
        "timeout": settings.embedding_timeout,
        "max_retries": 1,
        "check_embedding_ctx_length": False,
    }
    if settings.embedding_base_url:
        kwargs["base_url"] = settings.embedding_base_url
    return OpenAIEmbeddings(**kwargs)


def embed_documents(texts: list[str]) -> list[list[float]] | None:
    model = get_embedding_model()
    return model.embed_documents(texts) if model else None


def embed_query(text: str) -> list[float] | None:
    model = get_embedding_model()
    return model.embed_query(text) if model else None
