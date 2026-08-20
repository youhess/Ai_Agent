import asyncio

import pytest
from fastapi.testclient import TestClient

from agent.graph import agent_graph
from database.repository import get_case, replace_cases
from main import app
from scripts.generate_sample_data import generate


@pytest.fixture(autouse=True)
def fresh_workflow_case():
    replace_cases(generate())


def _run_agent(message: str):
    return asyncio.run(agent_graph.ainvoke({
        "user_query": message,
        "history": [],
        "tool_results": [],
        "retrieved_context": [],
        "execution_trace": [],
    }))


def test_agent_previews_write_action_without_mutating_until_confirmed():
    before = get_case("SG-DEMO-0001")
    state = _run_agent("协同派单 SG-DEMO-0001 至设施维护模拟组，协办社区网格模拟组")
    result = next(item["result"] for item in state["tool_results"] if item["tool"] == "advance_case_workflow")
    after = get_case("SG-DEMO-0001")

    assert before and before["status"] == "待处理"
    assert result["confirmation_required"] is True
    assert after and after["status"] == "待处理"
    assert after["timeline"] == before["timeline"]
    assert "尚未执行" in state["final_answer"]


def test_agent_analyses_context_before_suggesting_a_confirmable_dispatch():
    state = _run_agent("分析 SG-DEMO-0001 并给出协同派单方案")
    results = {item["tool"]: item["result"] for item in state["tool_results"]}

    assert state["plan"]["operation"] == "case_detail"
    assert results["recommend_case_collaboration"]["recommended_primary_unit"] == "设施维护模拟组"
    assert results["search_knowledge_base"]["count"] > 0
    assert "智能协同方案" in state["final_answer"]
    assert state["suggestions"][0].startswith("确认协同派单 SG-DEMO-0001")
    assert get_case("SG-DEMO-0001")["status"] == "待处理"


def test_agent_executes_traceable_collaboration_workflow_end_to_end():
    dispatched = _run_agent("确认协同派单 SG-DEMO-0001 至设施维护模拟组，协办社区网格模拟组")
    dispatch_result = next(item["result"] for item in dispatched["tool_results"] if item["tool"] == "advance_case_workflow")
    assert dispatch_result["success"] is True
    assert dispatch_result["case"]["status"] == "处理中"
    assert dispatch_result["case"]["collaborator_units"] == ["社区网格模拟组"]
    assert dispatch_result["case"]["timeline"][-1]["action"] == "智能协同派单"

    submitted = _run_agent("确认提交处置结果 SG-DEMO-0001，证据完整")
    submit_result = next(item["result"] for item in submitted["tool_results"] if item["tool"] == "advance_case_workflow")
    assert submit_result["success"] is True
    assert submit_result["case"]["evidence_complete"] is True
    assert submit_result["case"]["status"] == "处理中"

    closed = _run_agent("确认复核办结 SG-DEMO-0001")
    close_result = next(item["result"] for item in closed["tool_results"] if item["tool"] == "advance_case_workflow")
    assert close_result["success"] is True
    assert close_result["case"]["status"] == "已完成"
    assert close_result["case"]["resolved_at"]
    assert close_result["case"]["timeline"][-1]["action"] == "智能复核办结"
    assert "真实写入" in closed["final_answer"]


def test_api_rejects_closure_when_evidence_is_incomplete():
    with TestClient(app) as client:
        dispatch = client.post("/api/cases/SG-DEMO-0001/workflow", json={
            "action": "dispatch",
            "responsible_unit": "设施维护模拟组",
            "collaborator_units": ["社区网格模拟组", "物业协同模拟组"],
        })
        assert dispatch.status_code == 200
        close = client.post("/api/cases/SG-DEMO-0001/workflow", json={"action": "approve_close"})

    assert close.status_code == 409
    assert "证据尚不完整" in close.json()["detail"]
    case = get_case("SG-DEMO-0001")
    assert case and case["status"] == "处理中" and case["resolved_at"] is None
