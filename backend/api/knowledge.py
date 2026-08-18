from fastapi import APIRouter, Query

from rag.ingest import ingest_knowledge
from rag.retriever import retrieve

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/search")
def search_knowledge(q: str = Query(min_length=1), limit: int = Query(4, ge=1, le=10)):
    return {"items": retrieve(q, limit)}


@router.post("/ingest")
def ingest():
    return {"chunks": ingest_knowledge(), "message": "知识库索引已更新"}
