from fastapi import APIRouter, HTTPException, Query

from agent.tools.registry import get_tools
from business_config import BUSINESS_CONFIG
from config import get_settings
from database.admin_repository import get_agent_run, list_agent_runs
from rag.embeddings import embedding_configured
from rag.retriever import retrieval_status
from rag.vector_store import LocalVectorStore

router = APIRouter(prefix="/api/admin", tags=["admin-agent"])
RUN_STATUSES = {"running", "completed", "failed", "cancelled"}


@router.get("/agent/config")
def agent_config():
    settings = get_settings()
    store = LocalVectorStore()
    store.load()
    rag_status = retrieval_status()
    return {
        "agent_name": BUSINESS_CONFIG["agent_name"],
        "domain": BUSINESS_CONFIG["domain"],
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "llm_configured": bool(settings.llm_api_key),
        "embedding_configured": embedding_configured(),
        "retrieval_mode": store.mode,
        "rag_provider_mode": rag_status["provider_mode"],
        "xingchen_rag_configured": rag_status["xingchen_configured"],
        "rag_fallback_enabled": rag_status["fallback_enabled"],
        "rag_last_provider": rag_status["last_provider"],
        "rag_last_error": rag_status["last_error"],
        "rag_last_latency_ms": rag_status["last_latency_ms"],
        "rag_fallback_count": rag_status["fallback_count"],
        "tools": [{"name": tool.name, "description": tool.description} for tool in get_tools()],
        "editable": False,
    }


@router.get("/runs")
def runs(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status: str | None = None, query: str | None = Query(None, max_length=100),
):
    if status and status not in RUN_STATUSES:
        raise HTTPException(status_code=422, detail="运行状态不合法")
    return list_agent_runs(page=page, page_size=page_size, status=status, query=query)


@router.get("/runs/{run_id}")
def run_detail(run_id: str):
    result = get_agent_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return result
