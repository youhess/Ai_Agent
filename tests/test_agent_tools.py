import asyncio

from agent.graph import agent_graph
from agent.model import get_chat_model
from agent.tools.registry import TOOL_REGISTRY
from rag.retriever import retrieve


def test_tool_registry_and_patterned_trend():
    assert len(TOOL_REGISTRY) == 6
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
    assert data["intent"] == "data_query" and data["cases"]
    assert knowledge["intent"] == "knowledge_query" and knowledge["retrieved_context"]
    assert comprehensive["intent"] == "analysis_query"
    assert comprehensive["cases"] and comprehensive["retrieved_context"]
    assert get_chat_model() is None
