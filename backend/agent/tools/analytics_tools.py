from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool

from database.repository import query_cases
from services.analytics import calculate_statistics, calculate_trend, group_cases


@tool
def get_case_statistics(district: str | None = None, street: str | None = None, category: str | None = None,
                        statuses: list[str] | None = None, level: str | None = None, priority: str | None = None,
                        days: int | None = None, start_date: str | None = None,
                        end_date: str | None = None) -> dict[str, Any]:
    """计算过滤后事件总数、各维度分布与平均处理时长。"""
    return calculate_statistics(query_cases(
        district=district, street=street, category=category, statuses=statuses, level=level, priority=priority,
        days=days, start_date=start_date, end_date=end_date, limit=1000,
    ))


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


@tool
def aggregate_cases(district: str | None = None, street: str | None = None, category: str | None = None,
                    statuses: list[str] | None = None, level: str | None = None, priority: str | None = None,
                    days: int | None = None, start_date: str | None = None, end_date: str | None = None,
                    group_by: str = "category") -> dict[str, Any]:
    """筛选治理事件，并按区域、街道、类别、状态、优先级或日期聚合数量与占比。"""
    rows = query_cases(
        district=district, street=street, category=category, statuses=statuses, level=level, priority=priority,
        days=days, start_date=start_date, end_date=end_date, limit=1000,
    )
    return {"total": len(rows), "group_by": group_by, "groups": group_cases(rows, group_by)}


@tool
def compare_case_periods(district: str | None = None, street: str | None = None,
                         category: str | None = None, statuses: list[str] | None = None,
                         level: str | None = None, priority: str | None = None, current_start_date: str | None = None,
                         current_end_date: str | None = None, previous_start_date: str | None = None,
                         previous_end_date: str | None = None, days: int = 7,
                         group_by: str = "category") -> dict[str, Any]:
    """比较当前与上一时间段的事件数量，并返回分组变化。"""
    common = {"district": district, "street": street, "category": category, "statuses": statuses, "level": level, "priority": priority}
    if current_start_date and current_end_date and previous_start_date and previous_end_date:
        current = query_cases(**common, start_date=current_start_date, end_date=current_end_date, limit=1000)
        previous = query_cases(**common, start_date=previous_start_date, end_date=previous_end_date, limit=1000)
    else:
        rows = query_cases(**common, days=days * 2, limit=1000)
        now = datetime.now()
        current_start = now - timedelta(days=days)
        previous_start = now - timedelta(days=days * 2)
        current = [row for row in rows if datetime.fromisoformat(row["created_at"]) >= current_start]
        previous = [row for row in rows if previous_start <= datetime.fromisoformat(row["created_at"]) < current_start]
    def group_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        metrics: dict[str, dict[str, int]] = {}
        for row in rows:
            name = row["created_at"][:10] if group_by == "date" else str(row[group_by])
            item = metrics.setdefault(name, {"count": 0, "completed": 0})
            item["count"] += 1
            if row["status"] == "已完成":
                item["completed"] += 1
        return metrics

    current_groups = group_metrics(current)
    previous_groups = group_metrics(previous)
    groups = []
    for name in set(current_groups) | set(previous_groups):
        current_item = current_groups.get(name, {"count": 0, "completed": 0})
        previous_item = previous_groups.get(name, {"count": 0, "completed": 0})
        current_count = current_item["count"]
        previous_count = previous_item["count"]
        groups.append({
            "name": name, "current": current_count, "previous": previous_count,
            "delta": current_count - previous_count,
            "current_completed": current_item["completed"],
            "previous_completed": previous_item["completed"],
            "current_completion_rate": round(current_item["completed"] / current_count * 100, 1) if current_count else None,
            "previous_completion_rate": round(previous_item["completed"] / previous_count * 100, 1) if previous_count else None,
        })
    previous_total = len(previous)
    growth_rate = None if previous_total == 0 else round((len(current) - previous_total) / previous_total * 100, 1)
    current_completed = sum(1 for row in current if row["status"] == "已完成")
    previous_completed = sum(1 for row in previous if row["status"] == "已完成")
    return {
        "current_count": len(current), "previous_count": previous_total,
        "delta": len(current) - previous_total, "growth_rate": growth_rate,
        "current_completed": current_completed, "previous_completed": previous_completed,
        "current_completion_rate": round(current_completed / len(current) * 100, 1) if current else None,
        "previous_completion_rate": round(previous_completed / previous_total * 100, 1) if previous_total else None,
        "group_by": group_by, "groups": sorted(groups, key=lambda item: item["delta"], reverse=True),
    }


@tool
def find_recurring_locations(district: str | None = None, category: str | None = None,
                             days: int = 7, minimum_count: int = 3) -> dict[str, Any]:
    """按街道和类别识别最近一段时间内重复发生的治理问题。"""
    rows = query_cases(district=district, category=category, days=days, limit=1000)
    counts: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        counts.setdefault((row["street"], row["category"]), []).append(row)
    hotspots = [
        {"street": street, "category": item_category, "count": len(items), "latest_case": items[0]}
        for (street, item_category), items in counts.items() if len(items) >= minimum_count
    ]
    return {"days": days, "minimum_count": minimum_count, "location_granularity": "street", "hotspots": sorted(hotspots, key=lambda item: item["count"], reverse=True)}
