from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any


def _distribution(cases: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(case[field]) for case in cases))


def calculate_statistics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    resolution_hours = []
    for case in cases:
        if case.get("resolved_at"):
            start = datetime.fromisoformat(case["created_at"])
            end = datetime.fromisoformat(case["resolved_at"])
            resolution_hours.append((end - start).total_seconds() / 3600)
    return {
        "total": len(cases),
        "category_distribution": _distribution(cases, "category"),
        "district_distribution": _distribution(cases, "district"),
        "status_distribution": _distribution(cases, "status"),
        "priority_distribution": _distribution(cases, "priority"),
        "average_resolution_hours": round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None,
    }


def calculate_trend(cases: list[dict[str, Any]], days: int = 7) -> dict[str, Any]:
    now = datetime.now()
    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=days * 2)
    current = [case for case in cases if datetime.fromisoformat(case["created_at"]) >= current_start]
    previous = [case for case in cases if previous_start <= datetime.fromisoformat(case["created_at"]) < current_start]
    by_date: defaultdict[str, int] = defaultdict(int)
    for case in current:
        by_date[case["created_at"][:10]] += 1
    growth_rate = None if not previous else round((len(current) - len(previous)) / len(previous) * 100, 1)
    current_categories = Counter(case["category"] for case in current)
    previous_categories = Counter(case["category"] for case in previous)
    category_growth = {}
    for category in set(current_categories) | set(previous_categories):
        before = previous_categories[category]
        category_growth[category] = None if before == 0 else round((current_categories[category] - before) / before * 100, 1)
    anomalies = [
        {"category": category, "growth_rate": rate, "current_count": current_categories[category]}
        for category, rate in category_growth.items() if rate is not None and rate >= 40 and current_categories[category] >= 3
    ]
    return {
        "period_days": days,
        "current_count": len(current),
        "previous_count": len(previous),
        "growth_rate": growth_rate,
        "daily_counts": dict(sorted(by_date.items())),
        "category_growth": category_growth,
        "anomalies": sorted(anomalies, key=lambda item: item["growth_rate"], reverse=True),
    }
