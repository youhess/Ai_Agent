from config import get_settings
from rag.loader import load_directory
from rag.splitter import split_text
from rag.vector_store import LocalVectorStore


def ingest_knowledge() -> int:
    chunks = [
        {"document_name": name, "chunk": chunk, "chunk_id": f"{name}:{index}"}
        for name, text in load_directory(get_settings().knowledge_dir)
        for index, chunk in enumerate(split_text(text), start=1)
    ]
    LocalVectorStore().build(chunks)
    return len(chunks)


if __name__ == "__main__":
    print(f"Indexed {ingest_knowledge()} knowledge chunks.")
