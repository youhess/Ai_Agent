import re
import logging

from rag.embeddings import embed_query
from rag.vector_store import LocalVectorStore

logger = logging.getLogger(__name__)


def retrieve(query: str, limit: int = 4) -> list[dict]:
    normalized = re.sub(r"(?:请|帮我|检索|查找|查询|Demo|知识库|文档|资料|关于|里面|里|详细|相关|的条款)", "", query, flags=re.IGNORECASE).strip()
    search_text = normalized or query
    query_vector = None
    try:
        query_vector = embed_query(search_text)
    except Exception as exc:
        logger.warning("Embedding query failed, using lexical fallback: %s", exc)
    return LocalVectorStore().search(search_text, limit, query_embedding=query_vector)
