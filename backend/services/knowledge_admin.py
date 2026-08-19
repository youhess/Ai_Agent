from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from config import get_settings
from database.admin_repository import (
    delete_knowledge_document,
    find_knowledge_by_sha256,
    get_knowledge_document,
    list_knowledge_documents,
    upsert_knowledge_document,
)
from rag.ingest import SUPPORTED_SUFFIXES, discover_documents, rebuild_knowledge_index

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MIME_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
}


class KnowledgeAdminError(ValueError):
    pass


def _public_document(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key) for key in (
            "id", "file_name", "source_type", "size_bytes", "status", "chunk_count",
            "index_mode", "error_message", "created_at", "updated_at", "indexed_at",
        )
    }


def documents() -> dict[str, Any]:
    discover_documents()
    items = [_public_document(item) for item in list_knowledge_documents()]
    modes = {item["index_mode"] for item in items if item["status"] == "indexed"}
    mode = "hybrid" if "hybrid" in modes else "lexical"
    return {
        "items": items, "count": len(items), "index_mode": mode,
        "indexed_count": sum(item["status"] == "indexed" for item in items),
    }


def upload_document(file_name: str, content_type: str | None, content: bytes) -> dict[str, Any]:
    safe_name = Path(file_name or "document").name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise KnowledgeAdminError("仅支持 PDF、DOCX、TXT、MD 文件")
    if not content:
        raise KnowledgeAdminError("上传文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise KnowledgeAdminError("文件不能超过 20 MB")
    if content_type and content_type not in MIME_TYPES[suffix] | {"application/octet-stream"}:
        raise KnowledgeAdminError("文件类型与扩展名不匹配")
    discover_documents()
    sha256 = hashlib.sha256(content).hexdigest()
    duplicate = find_knowledge_by_sha256(sha256)
    if duplicate:
        raise KnowledgeAdminError(f"相同内容的文档“{duplicate['file_name']}”已经存在")

    document_id = uuid.uuid4().hex
    stored_name = f"{document_id}{suffix}"
    directory = get_settings().managed_knowledge_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / stored_name
    path.write_bytes(content)
    upsert_knowledge_document({
        "id": document_id, "file_name": safe_name, "stored_name": stored_name, "source_type": "uploaded",
        "sha256": sha256, "size_bytes": len(content), "status": "pending",
    })
    result = rebuild_knowledge_index()
    item = get_knowledge_document(document_id)
    return {"document": _public_document(item or {}), "index": result}


def remove_document(document_id: str) -> dict[str, Any]:
    document = get_knowledge_document(document_id)
    if not document:
        raise KnowledgeAdminError("文档不存在")
    if document["source_type"] != "uploaded":
        raise KnowledgeAdminError("内置资料不可删除")
    path = get_settings().managed_knowledge_dir / str(document["stored_name"])
    if not path.exists():
        raise KnowledgeAdminError("托管文件不存在，请检查数据目录")
    temporary = path.with_suffix(path.suffix + ".deleting")
    path.rename(temporary)
    try:
        result = rebuild_knowledge_index()
    except Exception as exc:
        temporary.rename(path)
        raise KnowledgeAdminError("索引重建异常，文档删除已撤销") from exc
    if not result["success"]:
        temporary.rename(path)
        raise KnowledgeAdminError("索引重建失败，文档删除已撤销")
    temporary.unlink(missing_ok=True)
    delete_knowledge_document(document_id)
    return {"deleted": document_id, "index": result}
