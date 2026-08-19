from typing import Any

from langchain_core.tools import tool

from database.repository import get_case, query_cases as repository_query_cases


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
