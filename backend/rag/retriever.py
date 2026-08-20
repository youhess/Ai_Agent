import re
import logging
import threading
import time
from typing import Any

from config import get_settings
from rag.embeddings import embed_query
from rag.vector_store import LocalVectorStore
from rag.xingchen import XingchenRagError, retrieve_from_xingchen, xingchen_configured

logger = logging.getLogger(__name__)
_runtime_lock = threading.Lock()
_runtime_state: dict[str, Any] = {
    "last_provider": None, "last_error": None, "last_latency_ms": None, "fallback_count": 0,
}


def _set_runtime_state(**updates: Any) -> None:
    with _runtime_lock:
        _runtime_state.update(updates)


def reset_retrieval_runtime_state() -> None:
    with _runtime_lock:
        _runtime_state.update({"last_provider": None, "last_error": None, "last_latency_ms": None, "fallback_count": 0})


def retrieval_status() -> dict[str, Any]:
    settings = get_settings()
    store = LocalVectorStore()
    store.load()
    provider = settings.rag_provider.strip().lower()
    if provider not in {"auto", "local", "xingchen"}:
        provider = "auto"
    with _runtime_lock:
        runtime = dict(_runtime_state)
    return {
        "provider_mode": provider,
        "xingchen_configured": xingchen_configured(),
        "local_mode": store.mode,
        "fallback_enabled": True,
        **runtime,
    }


def _retrieve_local(query: str, limit: int) -> list[dict]:
    normalized = re.sub(r"(?:请|帮我|检索|查找|查询|Demo|知识库|文档|资料|关于|里面|里|详细|相关|的条款)", "", query, flags=re.IGNORECASE).strip()
    search_text = normalized or query
    query_vector = None
    try:
        query_vector = embed_query(search_text)
    except Exception as exc:
        logger.warning("Embedding query failed, using lexical fallback: %s", exc)
    return LocalVectorStore().search(search_text, limit, query_embedding=query_vector)


def retrieve(query: str, limit: int = 4, context: dict[str, Any] | None = None) -> list[dict]:
    settings = get_settings()
    provider = settings.rag_provider.strip().lower()
    if provider not in {"auto", "local", "xingchen"}:
        logger.warning("Unknown RAG_PROVIDER=%s, using auto", provider)
        provider = "auto"
    remote_configured = xingchen_configured()
    should_try_remote = provider in {"auto", "xingchen"} and remote_configured
    if should_try_remote:
        started = time.perf_counter()
        try:
            remote_results = retrieve_from_xingchen(query, limit, context)
            latency = round((time.perf_counter() - started) * 1000)
            if remote_results:
                _set_runtime_state(last_provider="xingchen", last_error=None, last_latency_ms=latency)
                return remote_results
            _set_runtime_state(last_error="星辰 RAG 未返回可用结果", last_latency_ms=latency)
        except XingchenRagError as exc:
            latency = round((time.perf_counter() - started) * 1000)
            logger.warning("Xingchen RAG unavailable, using local fallback: %s", exc)
            _set_runtime_state(last_error=str(exc), last_latency_ms=latency)
    elif provider == "xingchen":
        _set_runtime_state(last_error="星辰 RAG API 尚未配置", last_latency_ms=None)

    local_results = _retrieve_local(query, limit)
    fallback_used = should_try_remote or provider == "xingchen"
    with _runtime_lock:
        fallback_count = int(_runtime_state.get("fallback_count") or 0) + (1 if fallback_used else 0)
    _set_runtime_state(
        last_provider="local_fallback" if fallback_used else "local",
        fallback_count=fallback_count,
    )
    return local_results
