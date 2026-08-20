from fastapi import APIRouter, HTTPException, Query

from agent.tools.case_tools import build_case_collaboration_recommendation
from database.repository import WorkflowConflict, advance_case_workflow, get_case, query_cases
from schemas.workflow import WorkflowActionRequest

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("")
def list_cases(district: str | None = None, category: str | None = None, status: str | None = None,
               priority: str | None = None, keyword: str | None = Query(None, max_length=100),
               days: int | None = Query(None, ge=1, le=3650),
               limit: int = Query(50, ge=1, le=500)):
    rows = query_cases(district=district, category=category, status=status, priority=priority, keyword=keyword, days=days, limit=limit)
    return {"items": rows, "count": len(rows)}


@router.get("/{case_id}")
def case_detail(case_id: str):
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="未找到该治理事件")
    return case


@router.get("/{case_id}/collaboration-recommendation")
def collaboration_recommendation(case_id: str):
    result = build_case_collaboration_recommendation(case_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail="未找到该治理事件")
    return result


@router.post("/{case_id}/workflow")
def execute_workflow_action(case_id: str, request: WorkflowActionRequest):
    try:
        case = advance_case_workflow(case_id, **request.model_dump())
    except WorkflowConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not case:
        raise HTTPException(status_code=404, detail="未找到该治理事件")
    return {"success": True, "action": request.action, "case": case}
