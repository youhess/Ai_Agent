from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from config import get_settings
from database.admin_repository import (
    find_knowledge_by_sha256,
    update_knowledge_status,
    upsert_knowledge_document,
)
from rag.embeddings import embed_documents
from rag.loader import load_document
from rag.splitter import split_text
from rag.vector_store import LocalVectorStore

logger = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf", ".docx"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_documents() -> list[dict[str, Any]]:
    settings = get_settings()
    locations = ((settings.knowledge_dir, "built_in"), (settings.managed_knowledge_dir, "uploaded"))
    documents: list[dict[str, Any]] = []
    for directory, source_type in locations:
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            sha256 = file_sha256(path)
            existing = find_knowledge_by_sha256(sha256)
            proposed_id = existing["id"] if existing else f"{source_type}-{sha256[:24]}"
            display_name = existing["file_name"] if existing else path.name
            upsert_knowledge_document({
                "id": proposed_id, "file_name": display_name, "stored_name": path.name,
                "source_type": source_type, "sha256": sha256, "size_bytes": path.stat().st_size,
                "status": "pending",
            })
            record = find_knowledge_by_sha256(sha256)
            if record:
                documents.append({**record, "path": path})
    return documents


def rebuild_knowledge_index() -> dict[str, Any]:
    documents = discover_documents()
    prepared: list[tuple[dict[str, Any], list[str]]] = []
    failures: list[dict[str, str]] = []
    for document in documents:
        try:
            chunks = split_text(load_document(document["path"]))
            if not chunks:
                raise ValueError("文档没有可索引文本")
            prepared.append((document, chunks))
        except Exception as exc:
            message = str(exc)[:300]
            update_knowledge_status(document["id"], status="failed", error_message=message)
            failures.append({"document_id": document["id"], "file_name": document["file_name"], "message": message})
    if failures:
        return {"success": False, "chunks": 0, "mode": "unchanged", "failures": failures}

    chunk_rows = [
        {
            "document_id": document["id"], "document_name": document["file_name"],
            "source_type": document["source_type"], "chunk": chunk,
            "chunk_id": f"{document['id']}:{index}",
        }
        for document, chunks in prepared
        for index, chunk in enumerate(chunks, start=1)
    ]
    vectors = None
    try:
        vectors = embed_documents([item["chunk"] for item in chunk_rows]) if chunk_rows else None
    except Exception as exc:
        logger.warning("Embedding build failed, creating lexical index: %s", exc)
    mode = LocalVectorStore().build(chunk_rows, vectors)
    counts = {document["id"]: len(chunks) for document, chunks in prepared}
    for document, _ in prepared:
        update_knowledge_status(
            document["id"], status="indexed", chunk_count=counts[document["id"]],
            index_mode=mode, error_message=None, indexed=True,
        )
    return {"success": True, "chunks": len(chunk_rows), "mode": mode, "failures": []}


def ingest_knowledge() -> int:
    result = rebuild_knowledge_index()
    if not result["success"]:
        names = "、".join(item["file_name"] for item in result["failures"])
        raise ValueError(f"知识文档解析失败：{names}")
    return int(result["chunks"])


if __name__ == "__main__":
    print(f"Indexed {ingest_knowledge()} knowledge chunks.")
