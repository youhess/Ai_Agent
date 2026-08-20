import asyncio

from agent.graph import agent_graph
from agent.model import get_chat_model
from agent.planner import build_deterministic_plan
from agent.tools.registry import TOOL_REGISTRY
from rag.retriever import retrieve


def test_tool_registry_and_patterned_trend():
    assert {
        "query_cases", "get_case_detail", "get_case_statistics", "analyse_case_trend",
        "get_high_risk_cases", "aggregate_cases", "compare_case_periods",
        "find_recurring_locations", "recommend_case_collaboration", "advance_case_workflow", "search_knowledge_base",
    } == set(TOOL_REGISTRY)
    trend = TOOL_REGISTRY["analyse_case_trend"].invoke({"district": "滨江区", "days": 7})
    assert trend["current_count"] > 0
    assert trend["growth_rate"] is not None
    assert any(item["category"] == "噪声扰民" for item in trend["anomalies"])


def test_rag_is_traceable():
    results = retrieve("高风险事件应该如何分级处置", 3)
    assert results
    assert all({"document_name", "chunk", "score"} <= item.keys() for item in results)
    assert any("分级规则" in item["document_name"] for item in results)


def test_three_core_graph_routes_without_external_llm():
    async def run():
        base = {"tool_results": [], "retrieved_context": [], "execution_trace": []}
        data = await agent_graph.ainvoke({**base, "user_query": "滨江区最近7天有多少治理事件？"})
        knowledge = await agent_graph.ainvoke({**base, "user_query": "高风险治理事件应该如何处理？"})
        comprehensive = await agent_graph.ainvoke({**base, "user_query": "分析滨江区最近7天的异常治理事件，并结合治理规范给出处理建议。"})
        return data, knowledge, comprehensive

    data, knowledge, comprehensive = asyncio.run(run())
    data_results = {item["tool"]: item["result"] for item in data["tool_results"]}
    assert data["intent"] == "data_query"
    assert data["plan"]["operation"] == "aggregate" and data_results["aggregate_cases"]["total"] > 0
    assert knowledge["intent"] == "knowledge_query" and knowledge["retrieved_context"]
    assert comprehensive["intent"] == "analysis_query"
    assert comprehensive["cases"] and comprehensive["retrieved_context"]
    assert get_chat_model() is None


def test_structured_planner_supports_dates_levels_followups_and_safety():
    detail = build_deterministic_plan("查询8月1日至8月7日的一级未办结事件")
    assert detail.filters.level == "一级"
    assert detail.filters.statuses == ["待处理", "处理中"]
    assert detail.filters.start_date and detail.filters.end_date

    followup = build_deterministic_plan("那滨江区呢？", [
        {"role": "user", "content": "统计最近7天各类事件数量"},
        {"role": "assistant", "content": "已完成统计"},
    ])
    assert followup.operation == "aggregate"
    assert followup.filters.days == 7 and followup.filters.district == "滨江区"

    unsafe = build_deterministic_plan("导出所有投诉人的姓名、手机号和精确住址")
    assert unsafe.operation == "refuse" and unsafe.intent == "unsafe"

    workflow = build_deterministic_plan("确认协同派单 SG-DEMO-0001 至设施维护模拟组，协办社区网格模拟组")
    assert workflow.operation == "workflow" and workflow.intent == "action_query"
    assert workflow.workflow_action == "dispatch" and workflow.confirmed is True
    assert workflow.responsible_unit == "设施维护模拟组"
    assert workflow.collaborator_units == ["社区网格模拟组"]


def test_case_detail_has_traceable_timeline_and_evidence_state():
    rows = TOOL_REGISTRY["query_cases"].invoke({"limit": 20})
    completed = next(row for row in rows if row["status"] == "已完成")
    detail = TOOL_REGISTRY["get_case_detail"].invoke({"case_id": completed["id"]})
    assert detail["responsible_unit"]
    assert isinstance(detail["evidence_complete"], bool)
    assert detail["timeline"][-1]["action"] == "复核办结"


def test_agent_recommends_explainable_primary_and_collaborating_units():
    result = TOOL_REGISTRY["recommend_case_collaboration"].invoke({"case_id": "SG-DEMO-0001"})
    assert result["recommended_primary_unit"] == "设施维护模拟组"
    assert result["recommended_collaborator_units"] == ["社区网格模拟组", "物业协同模拟组"]
    assert result["requires_human_confirmation"] is True
    assert any("重复上报" in item for item in result["basis"])


def test_period_comparison_includes_completion_rates():
    result = TOOL_REGISTRY["compare_case_periods"].invoke({"days": 7, "group_by": "street"})
    assert {"current_completion_rate", "previous_completion_rate", "groups"} <= result.keys()
    assert result["groups"]
    assert {"current_completed", "previous_completed"} <= result["groups"][0].keys()
