from rag.vector_store import LocalVectorStore


def retrieve(query: str, limit: int = 4) -> list[dict]:
    return LocalVectorStore().search(query, limit)
