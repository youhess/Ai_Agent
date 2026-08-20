import asyncio
import json
from pathlib import Path

import pytest

from agent.graph import _suggested_questions, agent_graph
from agent.planner import build_deterministic_plan
from rag.retriever import retrieve


QUESTIONS = {
    item["id"]: item["prompt"]
    for item in json.loads((Path(__file__).parent / "evaluation" / "questions.json").read_text(encoding="utf-8"))["questions"]
}

EXPECTED_OPERATIONS = {
    "DQ-001": "list_cases", "DQ-002": "aggregate", "DQ-003": "case_detail", "DQ-004": "aggregate",
    "CA-001": "comprehensive", "CA-002": "compare_periods", "CA-003": "recurring_locations", "CA-004": "comprehensive",
    "RG-001": "knowledge", "RG-002": "knowledge", "RG-003": "knowledge", "RG-004": "knowledge",
    "MT-001": "comprehensive", "MT-002": "recurring_locations", "MT-003": "compare_periods", "MT-004": "comprehensive",
    "ND-001": "comprehensive", "ND-002": "compare_periods", "ND-003": "case_detail", "ND-004": "knowledge",
    "SF-001": "refuse", "SF-002": "refuse", "SF-003": "refuse", "SF-004": "refuse",
}


@pytest.mark.parametrize("question_id", EXPECTED_OPERATIONS)
def test_evaluation_questions_have_expected_operation(question_id: str):
    assert build_deterministic_plan(QUESTIONS[question_id]).operation == EXPECTED_OPERATIONS[question_id]


def test_irrelevant_knowledge_query_returns_no_weak_matches():
    assert retrieve(QUESTIONS["ND-004"], 4) == []


def test_no_data_stops_causal_inference_and_safety_skips_tools():
    async def run():
        base = {"history": [], "tool_results": [], "retrieved_context": [], "execution_trace": []}
        no_data = await agent_graph.ainvoke({**base, "user_query": QUESTIONS["ND-001"]})
        unsafe = await agent_graph.ainvoke({**base, "user_query": QUESTIONS["SF-001"]})
        return no_data, unsafe

    no_data, unsafe = asyncio.run(run())
    assert "不会继续推断" in no_data["final_answer"]
    assert unsafe["plan"]["operation"] == "refuse"
    assert unsafe.get("tool_results") == []


def test_ranked_multi_tool_query_passes_top_group_into_followup():
    result = asyncio.run(agent_graph.ainvoke({
        "user_query": QUESTIONS["MT-001"], "history": [],
        "tool_results": [], "retrieved_context": [], "execution_trace": [],
    }))
    tools = {item["tool"]: item["result"] for item in result["tool_results"]}
    assert "aggregate_cases" in tools and "query_ranked_group_cases" in tools
    assert tools["query_ranked_group_cases"]["group"] == tools["aggregate_cases"]["groups"][0]["name"]
    assert tools["query_ranked_group_cases"]["count"] <= 3


def test_only_unmatched_questions_receive_recommendations():
    common = {"history": [], "tool_results": [], "retrieved_context": [], "execution_trace": []}
    unmatched = {
        **common, "user_query": "明天天气怎么样？",
        "plan": build_deterministic_plan("明天天气怎么样？").model_dump(),
    }
    greeting = {
        **common, "user_query": "你好",
        "plan": build_deterministic_plan("你好").model_dump(),
    }
    knowledge_miss = {
        **common, "user_query": "知识库里有没有月球停车规范？",
        "plan": build_deterministic_plan("知识库里有没有月球停车规范？").model_dump(),
    }
    assert len(_suggested_questions(unmatched)) == 3
    assert _suggested_questions(greeting) == []
    assert any("治理规范" in item for item in _suggested_questions(knowledge_miss))
