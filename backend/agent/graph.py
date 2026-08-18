from __future__ import annotations

import json
import logging
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.model import get_chat_model
from agent.prompts import SYSTEM_PROMPT
from agent.router import parse_query, route_query
from agent.state import AgentState
from agent.tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)


def trace(step: str, title: str, summary: str, status: str = "completed") -> dict[str, str]:
    return {"step": step, "title": title, "status": status, "summary": summary}


def parse_request(state: AgentState) -> dict:
    entities = parse_query(state["user_query"])
    labels = [str(value) for key, value in entities.items() if key != "parsed_at"]
    return {
        "entities": entities,
        "execution_trace": [trace("parse_request", "理解用户问题", " · ".join(labels) if labels else "已识别用户分析目标")],
    }


def route_intent(state: AgentState) -> dict:
    intent = route_query(state["user_query"])
    labels = {"general_chat": "一般咨询", "knowledge_query": "知识查询", "data_query": "数据查询", "analysis_query": "综合分析"}
    return {"intent": intent, "execution_trace": [trace("route_intent", "规划执行路径", labels[intent])]}


def choose_route(state: AgentState) -> Literal["general", "knowledge", "data", "comprehensive"]:
    return {"general_chat": "general", "knowledge_query": "knowledge", "data_query": "data", "analysis_query": "comprehensive"}[state["intent"]]


def data_query(state: AgentState) -> dict:
    filters = {key: value for key, value in state.get("entities", {}).items() if key in {"district", "category", "status", "priority", "days"}}
    cases = TOOL_REGISTRY["query_cases"].invoke({**filters, "limit": 1000})
    statistics = TOOL_REGISTRY["get_case_statistics"].invoke(filters)
    days = int(filters.get("days", 7))
    trend_filters = {key: value for key, value in filters.items() if key in {"district", "category"}}
    trend = TOOL_REGISTRY["analyse_case_trend"].invoke({**trend_filters, "days": days})
    risks = TOOL_REGISTRY["get_high_risk_cases"].invoke({"district": filters.get("district"), "days": filters.get("days"), "limit": 20})
    return {
        "cases": cases,
        "tool_results": [
            {"tool": "query_cases", "result": {"count": len(cases)}},
            {"tool": "get_case_statistics", "result": statistics},
            {"tool": "analyse_case_trend", "result": trend},
            {"tool": "get_high_risk_cases", "result": {"count": len(risks), "cases": risks}},
        ],
        "execution_trace": [trace("data_query", "查询并统计治理事件", f"找到 {len(cases)} 条记录，识别 {len(risks)} 条未完成高风险事件")],
    }


def knowledge_query(state: AgentState) -> dict:
    sources = TOOL_REGISTRY["search_knowledge_base"].invoke({"query": state["user_query"], "limit": 4})
    summary = f"找到 {len(sources)} 条模拟处置资料" if sources else "知识库无匹配结果"
    return {
        "retrieved_context": sources,
        "tool_results": [{"tool": "search_knowledge_base", "result": {"count": len(sources)}}],
        "execution_trace": [trace("knowledge_query", "检索治理知识库", summary)],
    }


def comprehensive_query(state: AgentState) -> dict:
    data = data_query(state)
    knowledge = knowledge_query(state)
    return {
        "cases": data["cases"],
        "tool_results": data["tool_results"] + knowledge["tool_results"],
        "retrieved_context": knowledge["retrieved_context"],
        "execution_trace": data["execution_trace"] + knowledge["execution_trace"],
    }


def analyse(state: AgentState) -> dict:
    results = {item["tool"]: item["result"] for item in state.get("tool_results", [])}
    statistics = results.get("get_case_statistics", {})
    trend = results.get("analyse_case_trend", {})
    analysis = {
        "statistics": statistics,
        "trend": trend,
        "high_risk_count": results.get("get_high_risk_cases", {}).get("count", 0),
        "top_category": max(statistics.get("category_distribution", {}), key=statistics.get("category_distribution", {}).get, default=None),
        "anomalies": trend.get("anomalies", []),
    }
    anomaly_text = f"识别 {len(analysis['anomalies'])} 项显著类别变化" if analysis["anomalies"] else "未发现达到规则阈值的类别突增"
    return {"analysis_result": analysis, "execution_trace": [trace("analyse", "执行趋势与异常分析", anomaly_text)]}


def _fallback_answer(state: AgentState) -> str:
    if state.get("intent") == "general_chat":
        return "我是社会治理分析助手，可以查询事件数据、分析趋势并检索 Demo 治理资料。请说明区域、时间范围或关注的问题类别。"
    analysis = state.get("analysis_result", {})
    stats = analysis.get("statistics", {})
    trend = analysis.get("trend", {})
    sources = state.get("retrieved_context", [])
    if state.get("intent") == "knowledge_query":
        if not sources:
            return "## 核心结论\n\n当前知识库未检索到足以支持回答的资料，请先执行知识库初始化或补充相关文档。"
        excerpts = "\n".join(f"- **《{item['document_name'].rsplit('.', 1)[0]}》**：{item['chunk'][:220]}..." for item in sources[:3])
        names = "\n".join(f"- 《{item['document_name'].rsplit('.', 1)[0]}》" for item in sources)
        return f"## 处置参考\n\n{excerpts}\n\n> 以上内容来自模拟竞赛 Demo 文档，不是真实法律或政府政策。\n\n## 信息来源\n\n{names}"
    total = stats.get("total", len(state.get("cases", [])))
    growth = trend.get("growth_rate")
    growth_text = "缺少上一周期数据，暂无法计算" if growth is None else f"较上一周期{'增长' if growth >= 0 else '下降'} {abs(growth):.1f}%"
    top_category = analysis.get("top_category") or "暂无"
    anomalies = analysis.get("anomalies", [])
    anomaly_text = "\n".join(f"- {item['category']}：本期 {item['current_count']} 条，增长 {item['growth_rate']}%" for item in anomalies) or "- 当前没有类别达到“增长至少 40% 且本期不少于 3 条”的异常规则。"
    source_names = sorted({item["document_name"].rsplit(".", 1)[0] for item in sources})
    source_text = "\n".join(["- 治理事件数据库"] + [f"- 《{name}》（模拟 Demo 文档）" for name in source_names])
    return f"""## 核心结论

筛选范围内共 {total} 条治理事件，主要类别为 **{top_category}**；{growth_text}。当前有 {analysis.get('high_risk_count', 0)} 条未完成高风险事件。

## 数据依据

- 事件总数：{total}
- 当前周期：{trend.get('current_count', total)} 条
- 上一周期：{trend.get('previous_count', 0)} 条
- 平均处理时长：{stats.get('average_resolution_hours') if stats.get('average_resolution_hours') is not None else '暂无可计算数据'} 小时

## 异常发现

{anomaly_text}

## 建议措施

1. 优先复核未完成高风险事件，明确责任人与处置时限。
2. 对增长较快类别按街道和发生时段进一步下钻，安排针对性巡查。
3. 依据检索到的 Demo 处置规范执行分级、留痕和闭环复核；如无资料支持，应由业务人员补充规则后再决策。

## 信息来源

{source_text}"""


async def generate_response(state: AgentState) -> dict:
    fallback = _fallback_answer(state)
    model = get_chat_model()
    answer = fallback
    if model is not None and state.get("intent") != "general_chat":
        evidence = {
            "question": state["user_query"],
            "analysis": state.get("analysis_result", {}),
            "knowledge": state.get("retrieved_context", []),
            "deterministic_draft": fallback,
        }
        try:
            response = await model.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content="请仅根据以下工具证据整理最终回答，不新增数字或规则：\n" + json.dumps(evidence, ensure_ascii=False, default=str)),
            ])
            answer = str(response.content)
        except Exception as exc:
            logger.warning("LLM unavailable, returning grounded fallback: %s", exc)
    return {"final_answer": answer, "execution_trace": [trace("generate_response", "生成治理分析", "已根据可验证数据与资料形成回答")]}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("parse_request", parse_request)
    graph.add_node("route_intent", route_intent)
    graph.add_node("data_query", data_query)
    graph.add_node("knowledge_query", knowledge_query)
    graph.add_node("comprehensive_query", comprehensive_query)
    graph.add_node("analyse", analyse)
    graph.add_node("generate_response", generate_response)
    graph.add_edge(START, "parse_request")
    graph.add_edge("parse_request", "route_intent")
    graph.add_conditional_edges("route_intent", choose_route, {
        "general": "generate_response", "knowledge": "knowledge_query",
        "data": "data_query", "comprehensive": "comprehensive_query",
    })
    graph.add_edge("knowledge_query", "analyse")
    graph.add_edge("data_query", "analyse")
    graph.add_edge("comprehensive_query", "analyse")
    graph.add_edge("analyse", "generate_response")
    graph.add_edge("generate_response", END)
    return graph.compile()


agent_graph = build_graph()
