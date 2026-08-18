from langchain_core.tools import tool

from rag.retriever import retrieve


@tool
def search_knowledge_base(query: str, limit: int = 4) -> list[dict]:
    """检索本地业务知识库，返回文档名、文本片段和相关性分数。"""
    return retrieve(query, limit)
