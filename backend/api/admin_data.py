from io import BytesIO

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from database.admin_repository import data_summary, paged_case_rows
from services.data_import import ImportValidationError, commit_import, preview_import, template_bytes

router = APIRouter(prefix="/api/admin/data", tags=["admin-data"])


@router.get("/summary")
def get_data_summary():
    return data_summary()


@router.get("/rows")
def get_data_rows(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    rows, total = paged_case_rows(page, page_size)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/template")
def download_template():
    return StreamingResponse(
        BytesIO(template_bytes()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=governance-events-template.xlsx"},
    )


@router.post("/imports/preview")
async def preview_dataset(file: UploadFile = File(...)):
    try:
        return preview_import(file.filename or "dataset", await file.read())
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="文件解析失败，请检查模板和文件内容") from exc


@router.post("/imports/{import_id}/commit")
def commit_dataset(import_id: str):
    try:
        return commit_import(import_id)
    except ImportValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
