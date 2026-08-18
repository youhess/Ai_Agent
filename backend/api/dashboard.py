from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter

from database.repository import query_cases

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary():
    cases = query_cases(limit=1000)
    today = datetime.now().date().isoformat()
    completed = sum(case["status"] == "已完成" for case in cases)
    trend = defaultdict(int)
    cutoff = datetime.now() - timedelta(days=13)
    for case in cases:
        if datetime.fromisoformat(case["created_at"]) >= cutoff:
            trend[case["created_at"][:10]] += 1
    dates = [(datetime.now().date() - timedelta(days=offset)).isoformat() for offset in range(13, -1, -1)]
    return {
        "metrics": {
            "total_cases": len(cases),
            "today_cases": sum(case["created_at"][:10] == today for case in cases),
            "pending_cases": sum(case["status"] != "已完成" for case in cases),
            "high_risk_cases": sum(case["priority"] == "高" and case["status"] != "已完成" for case in cases),
            "completion_rate": round(completed / len(cases) * 100, 1) if cases else 0,
        },
        "trend": [{"date": date, "count": trend[date]} for date in dates],
        "categories": [{"name": name, "value": value} for name, value in Counter(case["category"] for case in cases).most_common()],
        "districts": [{"name": name, "value": value} for name, value in Counter(case["district"] for case in cases).most_common()],
    }
