from typing import Any

from langchain_core.tools import tool

from database.repository import (
    WorkflowConflict,
    advance_case_workflow as repository_advance_case_workflow,
    get_case,
    query_cases as repository_query_cases,
)


COLLABORATION_ROUTES = {
    "市容环境": ("市容管理模拟组", ["社区网格模拟组"]),
    "垃圾堆放": ("环卫处置模拟组", ["社区网格模拟组"]),
    "道路设施": ("道路养护模拟组", ["社区网格模拟组", "物业协同模拟组"]),
    "噪声扰民": ("综合协调模拟组", ["社区网格模拟组"]),
    "占道经营": ("市容管理模拟组", ["社区网格模拟组"]),
    "停车问题": ("交通协调模拟组", ["社区网格模拟组"]),
    "公共设施损坏": ("设施维护模拟组", ["社区网格模拟组", "物业协同模拟组"]),
    "社区服务": ("社区服务模拟组", ["社区网格模拟组"]),
}


@tool
def query_cases(district: str | None = None, street: str | None = None, category: str | None = None,
                statuses: list[str] | None = None, level: str | None = None,
                priority: str | None = None, days: int | None = None,
                start_date: str | None = None, end_date: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """按区域、街道、类别、状态、优先级和时间范围查询治理事件。"""
    return repository_query_cases(
        district=district, street=street, category=category, statuses=statuses, level=level, priority=priority,
        days=days, start_date=start_date, end_date=end_date, limit=limit,
    )


@tool
def get_case_detail(case_id: str) -> dict[str, Any]:
    """按事件 ID 查询一条治理事件详情。"""
    return get_case(case_id) or {"error": "未找到事件"}


def build_case_collaboration_recommendation(case_id: str) -> dict[str, Any]:
    case = get_case(case_id)
    if not case:
        return {"error": "未找到事件", "case_id": case_id}
    primary, collaborators = COLLABORATION_ROUTES.get(
        case["category"], ("综合协调模拟组", ["社区网格模拟组"]),
    )
    basis = [f"事件类别为“{case['category']}”，匹配对应模拟处置职责"]
    if case.get("priority") == "高" or case.get("level") == "一级":
        basis.append("事件为一级/高风险，应优先签收并保留持续反馈轨迹")
    if any(item.get("action") == "重复核验" for item in case.get("timeline", [])) or "连续上报" in case.get("description", ""):
        basis.append("存在重复上报信号，需要属地网格参与核验并避免重复派单")
    if case.get("street"):
        basis.append(f"事件发生在{case['street']}，建议属地协办核对现场信息")
    return {
        "case_id": case_id,
        "current_status": case["status"],
        "recommended_primary_unit": primary,
        "recommended_collaborator_units": collaborators,
        "basis": basis,
        "requires_human_confirmation": True,
        "recommended_action": "dispatch" if case["status"] == "待处理" else "follow_current_workflow",
    }


@tool
def recommend_case_collaboration(case_id: str) -> dict[str, Any]:
    """结合事件类别、风险等级和处置轨迹，为单个事件生成可解释的主办与协办建议。"""
    return build_case_collaboration_recommendation(case_id)


@tool
def advance_case_workflow(
    case_id: str,
    action: str,
    confirmed: bool,
    responsible_unit: str | None = None,
    collaborator_units: list[str] | None = None,
    evidence_complete: bool | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """经工作人员明确确认后，执行协同派单、提交结果、退回补充或复核办结，并真实更新事件状态。"""
    current = get_case(case_id)
    if not current:
        return {"success": False, "case_id": case_id, "action": action, "error": "未找到事件"}
    if not confirmed:
        return {
            "success": False,
            "confirmation_required": True,
            "case_id": case_id,
            "action": action,
            "case": current,
            "message": "这是业务写操作，需要工作人员使用“确认”或“执行”明确授权",
        }
    try:
        case = repository_advance_case_workflow(
            case_id,
            action=action,
            responsible_unit=responsible_unit,
            collaborator_units=collaborator_units,
            evidence_complete=evidence_complete,
            note=note,
        )
    except WorkflowConflict as exc:
        return {"success": False, "case_id": case_id, "action": action, "error": str(exc)}
    if not case:
        return {"success": False, "case_id": case_id, "action": action, "error": "未找到事件"}
    return {"success": True, "case_id": case_id, "action": action, "case": case}
