import json
from types import SimpleNamespace

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
        case_id = response.json()["items"][0]["id"]
        keyword_result = client.get("/api/cases", params={"keyword": case_id}).json()
        assert keyword_result["count"] == 1
        assert keyword_result["items"][0]["id"] == case_id


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


def test_general_chat_accepts_history_and_has_natural_fallback():
    with TestClient(app) as client:
        response = client.post("/api/agent/stream", json={
            "message": "你好",
            "history": [
                {"role": "user", "content": "我主要关注滨江区"},
                {"role": "assistant", "content": "好的，我记住了。"},
            ],
        })
    assert response.status_code == 200
    events = _sse_events(response.text)
    answer = next(item["data"]["content"] for item in events if item["type"] == "answer")
    assert answer.startswith("你好")
    assert "trace" not in [item["type"] for item in events]


def test_model_tokens_are_forwarded_without_duplicate_final_answer(monkeypatch):
    class FakeGraph:
        async def astream(self, *_args, **_kwargs):
            yield "updates", {"parse_request": {"plan": {"operation": "chat"}, "execution_trace": []}}
            yield "messages", (SimpleNamespace(content="你"), {"langgraph_node": "generate_response"})
            yield "messages", (SimpleNamespace(content="好"), {"langgraph_node": "generate_response"})
            yield "updates", {"generate_response": {"final_answer": "你好", "execution_trace": []}}

    monkeypatch.setattr("api.agent.agent_graph", FakeGraph())
    with TestClient(app) as client:
        response = client.post("/api/agent/stream", json={"message": "你好"})
    answers = [item["data"]["content"] for item in _sse_events(response.text) if item["type"] == "answer"]
    assert answers == ["你", "好"]


def test_partial_model_stream_can_be_replaced_by_grounded_fallback(monkeypatch):
    class FailingGraph:
        async def astream(self, *_args, **_kwargs):
            yield "updates", {"parse_request": {"plan": {"operation": "aggregate"}, "execution_trace": []}}
            yield "messages", (SimpleNamespace(content="不完整"), {"langgraph_node": "generate_response"})
            yield "updates", {"generate_response": {
                "final_answer": "可靠兜底回答", "response_reset": True, "execution_trace": [],
            }}

    monkeypatch.setattr("api.agent.agent_graph", FailingGraph())
    with TestClient(app) as client:
        response = client.post("/api/agent/stream", json={"message": "统计事件"})
    answers = [item["data"] for item in _sse_events(response.text) if item["type"] == "answer"]
    assert answers == [
        {"content": "不完整", "delta": True},
        {"content": "可靠兜底回答", "reset": True},
    ]
