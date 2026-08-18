from fastapi import APIRouter, HTTPException, Query

from database.repository import get_case, query_cases

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("")
def list_cases(district: str | None = None, category: str | None = None, status: str | None = None,
               priority: str | None = None, days: int | None = Query(None, ge=1, le=3650),
               limit: int = Query(50, ge=1, le=500)):
    rows = query_cases(district=district, category=category, status=status, priority=priority, days=days, limit=limit)
    return {"items": rows, "count": len(rows)}


@router.get("/{case_id}")
def case_detail(case_id: str):
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="未找到该治理事件")
    return case
