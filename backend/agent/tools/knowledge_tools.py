from typing import Any

from langchain_core.tools import tool

from rag.retriever import retrieve


@tool
def search_knowledge_base(
    query: str, limit: int = 4, case_context: dict[str, Any] | None = None,
) -> list[dict]:
    """优先检索星辰向量知识库，异常时自动回退本地索引，并返回可追溯知识片段。"""
    return retrieve(query, limit, context=case_context)
