import json

from fastapi.testclient import TestClient

from main import app


def test_health_dashboard_and_cases():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        dashboard = client.get("/api/dashboard/summary").json()
        assert dashboard["metrics"]["total_cases"] == 240
        assert dashboard["trend"]
        response = client.get("/api/cases", params={"district": "滨江区", "days": 7})
        assert response.status_code == 200
        assert response.json()["count"] > 0
        assert all(item["district"] == "滨江区" for item in response.json()["items"])


def _sse_events(response_text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in response_text.splitlines() if line.startswith("data: ")]


def test_comprehensive_demo_stream():
    with TestClient(app) as client:
        response = client.post("/api/agent/stream", json={"message": "分析滨江区最近7天的异常治理事件，并结合治理规范给出处理建议。"})
    assert response.status_code == 200
    events = _sse_events(response.text)
    types = [item["type"] for item in events]
    assert types.count("trace") >= 6
    assert "source" in types
    assert "answer" in types
    assert types[-1] == "done"
    answer = next(item["data"]["content"] for item in events if item["type"] == "answer")
    assert "核心结论" in answer
    assert "治理事件数据库" in answer


def test_empty_question_is_validation_error():
    with TestClient(app) as client:
        response = client.post("/api/agent/stream", json={"message": "   "})
    assert response.status_code == 422
