from typing import Any

from langchain_core.tools import tool

from database.repository import query_cases
from services.analytics import calculate_statistics, calculate_trend


@tool
def get_case_statistics(district: str | None = None, category: str | None = None,
                        status: str | None = None, priority: str | None = None,
                        days: int | None = None) -> dict[str, Any]:
    """计算过滤后事件总数、各维度分布与平均处理时长。"""
    return calculate_statistics(query_cases(district=district, category=category, status=status, priority=priority, days=days, limit=1000))


@tool
def analyse_case_trend(district: str | None = None, category: str | None = None, days: int = 7) -> dict[str, Any]:
    """计算当前周期与上一周期的事件增长、日趋势及类别异常。"""
    cases = query_cases(district=district, category=category, days=days * 2, limit=1000)
    return calculate_trend(cases, days)


@tool
def get_high_risk_cases(district: str | None = None, days: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """查询高优先级且尚未完成的治理事件。"""
    rows = query_cases(district=district, priority="高", days=days, limit=200)
    return [row for row in rows if row["status"] != "已完成"][:limit]
