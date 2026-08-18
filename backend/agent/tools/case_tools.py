from typing import Any

from langchain_core.tools import tool

from database.repository import get_case, query_cases as repository_query_cases


@tool
def query_cases(district: str | None = None, category: str | None = None, status: str | None = None,
                priority: str | None = None, days: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """按区域、类别、状态、优先级和最近天数查询治理事件。"""
    return repository_query_cases(district=district, category=category, status=status, priority=priority, days=days, limit=limit)


@tool
def get_case_detail(case_id: str) -> dict[str, Any]:
    """按事件 ID 查询一条治理事件详情。"""
    return get_case(case_id) or {"error": "未找到事件"}
