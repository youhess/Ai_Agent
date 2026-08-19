from fastapi import APIRouter, File, HTTPException, UploadFile

from rag.ingest import rebuild_knowledge_index
from services.knowledge_admin import KnowledgeAdminError, documents, remove_document, upload_document

router = APIRouter(prefix="/api/admin/knowledge", tags=["admin-knowledge"])


@router.get("/documents")
def list_documents():
    return documents()


@router.post("/documents", status_code=201)
async def create_document(file: UploadFile = File(...)):
    try:
        return upload_document(file.filename or "document", file.content_type, await file.read())
    except KnowledgeAdminError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/documents/{document_id}")
def delete_document(document_id: str):
    try:
        return remove_document(document_id)
    except KnowledgeAdminError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/reindex")
def reindex_documents():
    result = rebuild_knowledge_index()
    if not result["success"]:
        raise HTTPException(status_code=422, detail={"message": "部分文档解析失败，旧索引保持不变", **result})
    return result
