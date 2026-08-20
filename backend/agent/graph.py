from __future__ import annotations

import json
import logging
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.model import get_chat_model
from agent.planner import QueryPlan, plan_query
from agent.prompts import SYSTEM_PROMPT
from agent.state import AgentState
from agent.tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)


def trace(step: str, title: str, summary: str, status: str = "completed") -> dict[str, str]:
    return {"step": step, "title": title, "status": status, "summary": summary}


def _knowledge_trace_summary(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "知识库无匹配结果"
    provider = "星辰向量库" if sources[0].get("retrieval_mode") == "xingchen" else "本地知识索引"
    return f"{provider}返回 {len(sources)} 条可追溯资料"


def _clean_filters(plan: QueryPlan) -> dict[str, Any]:
    return {key: value for key, value in plan.filters.model_dump().items() if value not in (None, [])}


def _filter_summary(plan: QueryPlan) -> str:
    values = _clean_filters(plan)
    labels = {
        "district": "区域", "street": "街道/社区", "category": "类别", "statuses": "状态",
        "level": "等级", "priority": "优先级", "days": "最近天数", "start_date": "开始", "end_date": "结束",
    }
    parts = []
    for key, value in values.items():
        shown = "、".join(value) if isinstance(value, list) else value
        parts.append(f"{labels[key]}：{shown}")
    return "；".join(parts) if parts else "全部 Demo 数据"


async def parse_request(state: AgentState) -> dict:
    plan = await plan_query(state["user_query"], state.get("history", []))
    entities = _clean_filters(plan)
    if plan.case_id:
        entities["case_id"] = plan.case_id
    if plan.group_by:
        entities["group_by"] = plan.group_by
    if plan.workflow_action:
        entities["workflow_action"] = plan.workflow_action
        entities["confirmed"] = plan.confirmed
        if plan.responsible_unit:
            entities["responsible_unit"] = plan.responsible_unit
        if plan.collaborator_units:
            entities["collaborator_units"] = plan.collaborator_units
    operation_labels = {
        "chat": "一般交流", "list_cases": "查询事件明细", "case_detail": "查询事件详情",
        "aggregate": "聚合统计", "compare_periods": "周期对比", "recurring_locations": "重复问题分析",
        "knowledge": "检索治理资料", "comprehensive": "综合分析", "workflow": "推进协同处置",
        "refuse": "安全边界处理",
    }
    return {
        "plan": plan.model_dump(),
        "intent": plan.intent,
        "entities": entities,
        "execution_trace": [trace("parse_request", "理解用户问题", f"{operation_labels[plan.operation]} · {_filter_summary(plan)}")],
    }


def choose_route(state: AgentState) -> Literal["respond", "knowledge", "tools"]:
    operation = state["plan"]["operation"]
    if operation in {"chat", "refuse"}:
        return "respond"
    if operation == "knowledge":
        return "knowledge"
    return "tools"


def knowledge_query(state: AgentState) -> dict:
    sources = TOOL_REGISTRY["search_knowledge_base"].invoke({"query": state["user_query"], "limit": 4})
    summary = _knowledge_trace_summary(sources)
    return {
        "retrieved_context": sources,
        "tool_results": [{"tool": "search_knowledge_base", "result": {"count": len(sources)}}],
        "execution_trace": [trace("knowledge_query", "检索治理知识库", summary)],
    }


def _run_comprehensive(state: AgentState, plan: QueryPlan, filters: dict[str, Any]) -> dict:
    ranked_followup = bool(plan.group_by and "最多" in state["user_query"])
    base_filters = dict(filters)
    if ranked_followup:
        base_filters.pop("statuses", None)
    rows = TOOL_REGISTRY["query_cases"].invoke({**base_filters, "limit": 1000})
    statistics = TOOL_REGISTRY["get_case_statistics"].invoke(base_filters)
    results: list[dict[str, Any]] = [
        {"tool": "query_cases", "result": {"count": len(rows)}},
        {"tool": "get_case_statistics", "result": statistics},
    ]
    traces = [
        trace("query_cases", "查询治理事件", f"找到 {len(rows)} 条记录"),
        trace("get_case_statistics", "计算事件指标", f"完成 {len(rows)} 条记录的分布统计"),
    ]
    if plan.filters.start_date and plan.filters.end_date and plan.comparison_start_date and plan.comparison_end_date:
        compare_args = {key: value for key, value in base_filters.items() if key not in {"days", "start_date", "end_date"}}
        compare_args.update({
            "current_start_date": plan.filters.start_date,
            "current_end_date": plan.filters.end_date,
            "previous_start_date": plan.comparison_start_date,
            "previous_end_date": plan.comparison_end_date,
            "group_by": plan.group_by or "category",
        })
        comparison = TOOL_REGISTRY["compare_case_periods"].invoke(compare_args)
        results.append({"tool": "compare_case_periods", "result": comparison})
        traces.append(trace("compare_case_periods", "对比当前与上一周期", f"数量变化 {comparison['delta']:+d} 条"))
    else:
        trend_args = {key: value for key, value in base_filters.items() if key in {"district", "category", "days"}}
        trend = TOOL_REGISTRY["analyse_case_trend"].invoke({**trend_args, "days": int(trend_args.get("days", 7))})
        results.append({"tool": "analyse_case_trend", "result": trend})
        traces.append(trace("analyse_case_trend", "分析事件变化趋势", f"当前周期 {trend['current_count']} 条"))
    high_risk_count = sum(1 for row in rows if row["priority"] == "高" and row["status"] != "已完成")
    results.append({"tool": "high_risk_from_query", "result": {"count": high_risk_count}})
    if plan.group_by:
        aggregation = TOOL_REGISTRY["aggregate_cases"].invoke({**base_filters, "group_by": plan.group_by})
        results.append({"tool": "aggregate_cases", "result": aggregation})
        traces.append(trace("aggregate_cases", "执行分组统计", f"形成 {len(aggregation['groups'])} 个分组"))
        if ranked_followup and aggregation["groups"]:
            top_group = aggregation["groups"][0]["name"]
            followup_filters = dict(base_filters)
            followup_filters[plan.group_by] = top_group
            if plan.filters.statuses:
                followup_filters["statuses"] = plan.filters.statuses
            followup_rows = TOOL_REGISTRY["query_cases"].invoke({**followup_filters, "limit": plan.limit})
            results.append({"tool": "query_ranked_group_cases", "result": {"group": top_group, "count": len(followup_rows), "cases": followup_rows}})
            traces.append(trace("query_ranked_group_cases", "查询重点分组事件", f"{top_group} 返回 {len(followup_rows)} 条记录"))
    sources: list[dict[str, Any]] = []
    if plan.needs_knowledge:
        sources = TOOL_REGISTRY["search_knowledge_base"].invoke({"query": state["user_query"], "limit": 4})
        results.append({"tool": "search_knowledge_base", "result": {"count": len(sources)}})
        traces.append(trace("search_knowledge_base", "检索治理知识库", _knowledge_trace_summary(sources)))
    return {"cases": rows, "tool_results": results, "retrieved_context": sources, "execution_trace": traces}


def execute_plan(state: AgentState) -> dict:
    plan = QueryPlan.model_validate(state["plan"])
    filters = _clean_filters(plan)
    operation = plan.operation
    if operation == "workflow":
        result = TOOL_REGISTRY["advance_case_workflow"].invoke({
            "case_id": plan.case_id,
            "action": plan.workflow_action,
            "confirmed": plan.confirmed,
            "responsible_unit": plan.responsible_unit,
            "collaborator_units": plan.collaborator_units,
            "evidence_complete": plan.evidence_complete,
            "note": plan.workflow_note,
        })
        if result.get("success"):
            detail = result["case"]
            summary = f"事件状态已写入为“{detail['status']}”，处置轨迹已更新"
            action_trace = trace("advance_case_workflow", "执行协同治理动作", summary)
        elif result.get("confirmation_required"):
            detail = result.get("case")
            action_trace = trace("prepare_case_workflow", "生成业务操作预览", "等待工作人员明确确认，尚未修改事件")
        else:
            detail = None
            action_trace = trace("advance_case_workflow", "校验协同治理动作", result.get("error", "操作未执行"), "error")
        return {
            "cases": [detail] if detail else [],
            "tool_results": [{"tool": "advance_case_workflow", "result": result}],
            "execution_trace": [action_trace],
        }
    if operation == "case_detail":
        detail = TOOL_REGISTRY["get_case_detail"].invoke({"case_id": plan.case_id})
        found = "error" not in detail
        results = [{"tool": "get_case_detail", "result": detail}]
        traces = [trace("get_case_detail", "查询事件详情", "已找到事件" if found else "未找到指定事件")]
        sources: list[dict[str, Any]] = []
        wants_collaboration = any(word in state["user_query"] for word in ["派单建议", "协同派单", "协同方案", "主办单位", "协办单位", "分析", "研判"])
        if found and wants_collaboration:
            recommendation = TOOL_REGISTRY["recommend_case_collaboration"].invoke({"case_id": plan.case_id})
            results.append({"tool": "recommend_case_collaboration", "result": recommendation})
            traces.append(trace("recommend_case_collaboration", "研判主协办方案", f"建议由{recommendation['recommended_primary_unit']}主办"))
        if found and plan.needs_knowledge:
            case_context = {
                key: detail.get(key) for key in (
                    "id", "category", "district", "street", "level", "priority", "status", "responsible_unit",
                )
            }
            sources = TOOL_REGISTRY["search_knowledge_base"].invoke({
                "query": state["user_query"], "limit": 4, "case_context": case_context,
            })
            results.append({"tool": "search_knowledge_base", "result": {"count": len(sources)}})
            traces.append(trace("search_knowledge_base", "检索协同处置规则", _knowledge_trace_summary(sources)))
        return {
            "cases": [detail] if found else [],
            "tool_results": results,
            "retrieved_context": sources,
            "execution_trace": traces,
        }
    if operation == "list_cases":
        rows = TOOL_REGISTRY["query_cases"].invoke({**filters, "limit": plan.limit})
        return {
            "cases": rows,
            "tool_results": [{"tool": "query_cases", "result": {"count": len(rows)}}],
            "execution_trace": [trace("query_cases", "查询事件明细", f"返回 {len(rows)} 条记录")],
        }
    if operation == "aggregate":
        result = TOOL_REGISTRY["aggregate_cases"].invoke({**filters, "group_by": plan.group_by or "category"})
        return {
            "tool_results": [{"tool": "aggregate_cases", "result": result}],
            "execution_trace": [trace("aggregate_cases", "聚合治理事件", f"共 {result['total']} 条，形成 {len(result['groups'])} 个分组")],
        }
    if operation == "compare_periods":
        compare_filters = {key: value for key, value in filters.items() if key not in {"days", "start_date", "end_date"}}
        result = TOOL_REGISTRY["compare_case_periods"].invoke({
            **compare_filters,
            "current_start_date": plan.filters.start_date,
            "current_end_date": plan.filters.end_date,
            "previous_start_date": plan.comparison_start_date,
            "previous_end_date": plan.comparison_end_date,
            "days": plan.filters.days or 7,
            "group_by": plan.group_by or "category",
        })
        updates: dict[str, Any] = {
            "tool_results": [{"tool": "compare_case_periods", "result": result}],
            "execution_trace": [trace("compare_case_periods", "比较两个时间周期", f"数量变化 {result['delta']:+d} 条")],
        }
        if plan.needs_knowledge and result["delta"] > 0:
            sources = TOOL_REGISTRY["search_knowledge_base"].invoke({"query": state["user_query"], "limit": 4})
            updates["retrieved_context"] = sources
            updates["tool_results"].append({"tool": "search_knowledge_base", "result": {"count": len(sources)}})
            updates["execution_trace"].append(trace("search_knowledge_base", "检索治理知识库", _knowledge_trace_summary(sources)))
        return updates
    if operation == "recurring_locations":
        result = TOOL_REGISTRY["find_recurring_locations"].invoke({
            "district": plan.filters.district,
            "category": plan.filters.category,
            "days": plan.filters.days or 7,
            "minimum_count": 3,
        })
        updates: dict[str, Any] = {
            "tool_results": [{"tool": "find_recurring_locations", "result": result}],
            "execution_trace": [trace("find_recurring_locations", "识别重复发生问题", f"找到 {len(result['hotspots'])} 个街道级热点")],
        }
        if plan.needs_knowledge:
            sources = TOOL_REGISTRY["search_knowledge_base"].invoke({"query": state["user_query"], "limit": 4})
            updates["retrieved_context"] = sources
            updates["tool_results"].append({"tool": "search_knowledge_base", "result": {"count": len(sources)}})
            updates["execution_trace"].append(trace("search_knowledge_base", "检索治理知识库", _knowledge_trace_summary(sources)))
        return updates
    return _run_comprehensive(state, plan, filters)


def analyse(state: AgentState) -> dict:
    plan = QueryPlan.model_validate(state["plan"])
    results = {item["tool"]: item["result"] for item in state.get("tool_results", [])}
    statistics = results.get("get_case_statistics", {})
    trend = results.get("analyse_case_trend", results.get("compare_case_periods", {}))
    category_distribution = statistics.get("category_distribution", {})
    analysis = {
        "operation": plan.operation,
        "statistics": statistics,
        "trend": trend,
        "high_risk_count": results.get("high_risk_from_query", {}).get("count", 0),
        "top_category": max(category_distribution, key=category_distribution.get, default=None),
        "anomalies": trend.get("anomalies", []),
    }
    if plan.operation == "workflow":
        result = results.get("advance_case_workflow", {})
        summary = "业务状态与最新处置轨迹已复核" if result.get("success") else "已核验操作条件与人工确认状态"
        return {"analysis_result": analysis, "execution_trace": [trace("analyse", "核验业务状态", summary)]}
    return {"analysis_result": analysis, "execution_trace": [trace("analyse", "整理查询证据", "已形成可追溯的回答依据")]}


def _format_case_table(rows: list[dict[str, Any]], limit: int = 10) -> str:
    lines = ["| 事件编号 | 时间 | 区域 | 类别 | 等级 | 状态 |", "| --- | --- | --- | --- | --- | --- |"]
    for row in rows[:limit]:
        area = f"{row.get('district', '-')}·{row.get('street', '-')}"
        lines.append(f"| {row.get('id', '-')} | {str(row.get('created_at', '-'))[:16].replace('T', ' ')} | {area} | {row.get('category', '-')} | {row.get('level', row.get('priority', '-'))} | {row.get('status', '-')} |")
    return "\n".join(lines)


def _knowledge_fallback(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "当前知识库未检索到足以支持回答的资料，请补充相关 Demo 文档或调整问题。"
    excerpts = "\n".join(f"- **《{item['document_name'].rsplit('.', 1)[0]}》**：{item['chunk'][:220]}..." for item in sources[:3])
    return f"## 处置参考\n\n{excerpts}\n\n> 以上内容来自虚构竞赛 Demo 文档，不是真实法律、政策或现实处置指令。"


GENERAL_SUGGESTIONS = [
    "最近7天各区域事件数量是多少？",
    "目前有哪些高风险待处理事件？",
    "哪个事件类别增长最快？",
]
KNOWLEDGE_SUGGESTIONS = [
    "根据治理规范，高风险事件应该如何处理？",
    "治理事件办结需要保留哪些证据？",
    "知识库中有哪些事件分级规则？",
]


def _suggested_questions(state: AgentState) -> list[str]:
    plan = QueryPlan.model_validate(state["plan"])
    query = state["user_query"].strip().lower()
    results = {item["tool"]: item["result"] for item in state.get("tool_results", [])}
    if plan.operation == "workflow":
        workflow = results.get("advance_case_workflow", {})
        case = workflow.get("case") or {}
        case_id = case.get("id") or plan.case_id
        if workflow.get("confirmation_required"):
            return []
        if workflow.get("success") and case.get("status") == "处理中" and not case.get("evidence_complete"):
            return [f"确认提交处置结果 {case_id}，证据完整"]
        if workflow.get("success") and case.get("status") == "处理中" and case.get("evidence_complete"):
            return [f"确认复核办结 {case_id}", f"确认复核退回补充 {case_id}"]
        if workflow.get("success") and case.get("status") == "已完成":
            return [f"查询 {case_id} 的完整处置轨迹"]
        return []
    if plan.operation == "chat":
        understood_chat = any(word in query for word in [
            "你好", "您好", "hi", "hello", "在吗", "谢谢", "感谢", "辛苦了",
            "能做什么", "可以做什么", "有什么功能", "怎么使用", "使用帮助",
        ])
        return [] if understood_chat else GENERAL_SUGGESTIONS
    if plan.operation == "knowledge" and not state.get("retrieved_context"):
        return KNOWLEDGE_SUGGESTIONS
    if plan.operation == "case_detail" and "error" in results.get("get_case_detail", {}):
        return ["查询最近上报的治理事件", *GENERAL_SUGGESTIONS[:2]]
    if plan.operation == "case_detail" and results.get("recommend_case_collaboration", {}).get("recommended_action") == "dispatch":
        recommendation = results["recommend_case_collaboration"]
        collaborators = "、".join(recommendation.get("recommended_collaborator_units", []))
        command = f"确认协同派单 {plan.case_id} 至{recommendation['recommended_primary_unit']}"
        if collaborators:
            command += f"，协办{collaborators}"
        return [command]
    if plan.operation == "list_cases" and not state.get("cases"):
        return GENERAL_SUGGESTIONS
    if plan.operation == "aggregate" and not results.get("aggregate_cases", {}).get("total"):
        return GENERAL_SUGGESTIONS
    if plan.operation == "compare_periods":
        comparison = results.get("compare_case_periods", {})
        if comparison.get("current_count", 0) == 0 and comparison.get("previous_count", 0) == 0:
            return GENERAL_SUGGESTIONS
    if plan.operation == "recurring_locations" and not results.get("find_recurring_locations", {}).get("hotspots"):
        return GENERAL_SUGGESTIONS
    if plan.operation == "comprehensive" and not state.get("analysis_result", {}).get("statistics", {}).get("total"):
        return GENERAL_SUGGESTIONS
    return []


def _fallback_answer(state: AgentState) -> str:
    plan = QueryPlan.model_validate(state["plan"])
    query = state["user_query"].strip()
    if plan.operation == "refuse":
        return f"我不能按这个要求操作：{plan.safety_reason or '该请求超出了安全与业务权限边界'}。我可以改为提供脱敏汇总、模拟流程说明或建议联系有权限的专业人员。"
    if plan.operation == "chat":
        if any(word in query for word in ["谢谢", "感谢", "辛苦了"]):
            return "不客气。你可以继续问我事件数据、变化趋势或治理处置规范。"
        if any(word in query.lower() for word in ["你好", "您好", "hi", "hello", "在吗"]):
            return "你好！我是 AI智能助手“小智”。你可以直接问我某个区域的事件情况、近期趋势，或者具体事件的处置建议。"
        return "我可以帮你查询治理事件、分析趋势和检索 Demo 治理资料。你想先看哪个区域、时间范围或问题类别？"
    sources = state.get("retrieved_context", [])
    if plan.operation == "knowledge":
        return _knowledge_fallback(sources)
    results = {item["tool"]: item["result"] for item in state.get("tool_results", [])}
    if plan.operation == "workflow":
        result = results.get("advance_case_workflow", {})
        if result.get("error"):
            return f"事件 **{plan.case_id or '-'}** 的协同处置操作未执行：{result['error']}。业务状态没有发生变化。"
        case = result.get("case", {})
        action_labels = {
            "dispatch": "协同派单", "submit_result": "提交处置结果",
            "return_for_rework": "复核退回补充", "approve_close": "复核办结",
        }
        action_label = action_labels.get(plan.workflow_action, "业务操作")
        primary = plan.responsible_unit or case.get("responsible_unit") or "待明确"
        collaborators = plan.collaborator_units or case.get("collaborator_units") or []
        if result.get("confirmation_required"):
            details = [f"- 当前状态：{case.get('status', '-')}", f"- 拟执行动作：{action_label}"]
            if plan.workflow_action == "dispatch":
                details.append(f"- 主办单位：{primary}")
                details.append(f"- 协办单位：{'、'.join(collaborators) if collaborators else '未设置'}")
            if plan.workflow_action == "submit_result":
                evidence_text = "完整" if plan.evidence_complete is True else "待补充" if plan.evidence_complete is False else "尚未明确"
                details.append(f"- 证据状态：{evidence_text}")
            command = f"确认{action_label} {case.get('id', plan.case_id)}"
            if plan.workflow_action == "dispatch" and primary != "待明确":
                command += f" 至{primary}"
            if plan.workflow_action == "submit_result" and plan.evidence_complete is not None:
                command += "，证据完整" if plan.evidence_complete else "，证据待补充"
            return "## 操作预览\n\n" + "\n".join(details) + f"\n\n这是会改变业务状态的操作，目前**尚未执行**。如确认无误，请回复：`{command}`。"
        if result.get("success"):
            latest = case.get("timeline", [])[-1] if case.get("timeline") else {}
            return f"""## {action_label}已执行

事件 **{case.get('id')}** 的业务状态已经真实写入本地数据库。

- 当前状态：**{case.get('status')}**
- 主办单位：{case.get('responsible_unit') or '-'}
- 协办单位：{'、'.join(case.get('collaborator_units') or []) or '无'}
- 证据状态：{'完整' if case.get('evidence_complete') else '待补充'}
- 最新轨迹：{latest.get('action', '-')} · {latest.get('note', '-')}

> 本次动作由工作人员明确确认，执行结果已进入事件处置轨迹，可在“事件中心”查看。"""
        return f"事件 **{plan.case_id or '-'}** 的操作没有执行，请检查操作参数后重试。"
    if plan.operation == "case_detail":
        detail = results.get("get_case_detail", {})
        if "error" in detail:
            return f"当前 Demo 数据中未找到事件 **{plan.case_id}**。请核对事件编号后重试。"
        resolved = detail.get("resolved_at") or "尚未办结"
        timeline = "\n".join(
            f"- {item['occurred_at']} · {item['action']}（{item['operator_role']}）：{item['note']}"
            for item in detail.get("timeline", [])
        ) or "- 当前没有处置节点记录"
        answer = f"""事件 **{detail['id']}** 当前状态为 **{detail['status']}**，优先级为 **{detail['priority']}**。

- 区域：{detail['district']} · {detail['street']}
- 类别：{detail['category']}
- 上报时间：{detail['created_at']}
- 事件描述：{detail['description']}
- 事件等级：{detail.get('level', '-')}
- 责任单位：{detail.get('responsible_unit', '-')}
- 证据状态：{'完整' if detail.get('evidence_complete') else '待补充'}
- 办结时间：{resolved}
- 来源：{detail['source']}

### 处置轨迹

{timeline}"""
        recommendation = results.get("recommend_case_collaboration")
        if recommendation and "error" not in recommendation:
            basis = "\n".join(f"- {item}" for item in recommendation.get("basis", []))
            answer += f"""

### 智能协同方案

- 建议主办：**{recommendation['recommended_primary_unit']}**
- 建议协办：{'、'.join(recommendation.get('recommended_collaborator_units', [])) or '无'}
- 人工确认：执行前必须确认

研判依据：

{basis}"""
        if sources:
            answer += "\n\n" + _knowledge_fallback(sources)
        return answer
    if plan.operation == "list_cases":
        rows = state.get("cases", [])
        if not rows:
            return f"当前 Demo 数据中未检索到符合条件的事件。查询范围：{_filter_summary(plan)}。"
        return f"共找到 **{len(rows)}** 条事件，按上报时间倒序展示：\n\n{_format_case_table(rows)}"
    if plan.operation == "aggregate":
        result = results.get("aggregate_cases", {})
        if not result.get("total"):
            return f"当前 Demo 数据中没有符合条件的事件。查询范围：{_filter_summary(plan)}。"
        lines = "\n".join(f"- {item['name']}：{item['count']} 条（{item['percentage']}%）" for item in result.get("groups", []))
        return f"筛选范围内共 **{result['total']}** 条事件。\n\n{lines}"
    if plan.operation == "compare_periods":
        result = results.get("compare_case_periods", {})
        if result.get("current_count", 0) == 0 and result.get("previous_count", 0) == 0:
            return f"当前 Demo 数据在两个对比周期内都没有符合条件的事件。查询范围：{_filter_summary(plan)}。因此无法验证数量差异，也不会推断原因。"
        growth = result.get("growth_rate")
        growth_text = "上一周期为 0，无法计算变化率" if growth is None else f"变化率为 {growth:+.1f}%"
        if "办结" in query:
            group_lines = "\n".join(
                f"- {item['name']}：本期 {item['current_completed']}/{item['current']} 条办结（{item['current_completion_rate'] if item['current_completion_rate'] is not None else '-'}%），"
                f"上期 {item['previous_completed']}/{item['previous']} 条办结（{item['previous_completion_rate'] if item['previous_completion_rate'] is not None else '-'}%）"
                for item in result.get("groups", [])[:10]
            )
        else:
            group_lines = "\n".join(f"- {item['name']}：本期 {item['current']} 条，上期 {item['previous']} 条，变化 {item['delta']:+d}" for item in result.get("groups", [])[:10])
        answer = f"本期 **{result.get('current_count', 0)}** 条，上期 **{result.get('previous_count', 0)}** 条，净变化 **{result.get('delta', 0):+d}** 条；{growth_text}。"
        if group_lines:
            answer += f"\n\n{group_lines}"
        if sources:
            answer += "\n\n" + _knowledge_fallback(sources)
        return answer
    if plan.operation == "recurring_locations":
        result = results.get("find_recurring_locations", {})
        hotspots = result.get("hotspots", [])
        if not hotspots:
            return f"最近 {result.get('days', plan.filters.days or 7)} 天没有街道与同类别组合达到 {result.get('minimum_count', 3)} 次。当前数据仅精确到街道，不能进一步判断具体点位。"
        lines = "\n".join(f"- {item['street']} · {item['category']}：{item['count']} 次，最新事件 {item['latest_case']['id']}" for item in hotspots[:10])
        answer = f"按当前数据可用的街道粒度，共识别 **{len(hotspots)}** 个重复问题热点：\n\n{lines}"
        if sources:
            answer += "\n\n" + _knowledge_fallback(sources)
        return answer
    ranked_result = results.get("query_ranked_group_cases")
    if ranked_result:
        aggregation = results.get("aggregate_cases", {})
        top = aggregation.get("groups", [{}])[0]
        rows = ranked_result.get("cases", [])
        answer = f"事件最多的{('街道' if plan.group_by == 'street' else '分组')}是 **{ranked_result['group']}**，共 **{top.get('count', 0)}** 条。"
        if rows:
            answer += f"以下是该分组符合后续条件的前 {len(rows)} 条事件：\n\n{_format_case_table(rows, plan.limit)}"
        else:
            answer += "该分组当前没有符合后续条件的事件。"
        if sources:
            answer += "\n\n" + _knowledge_fallback(sources)
        return answer
    analysis = state.get("analysis_result", {})
    stats = analysis.get("statistics", {})
    trend = analysis.get("trend", {})
    total = stats.get("total", len(state.get("cases", [])))
    if total == 0:
        return f"当前 Demo 数据中未检索到符合条件的事件。查询范围：{_filter_summary(plan)}。由于没有事实数据，我不会继续推断增长原因或生成数据结论。"
    growth = trend.get("growth_rate")
    growth_text = "缺少可比数据，暂无法计算变化率" if growth is None else f"较上一周期{'增长' if growth >= 0 else '下降'} {abs(growth):.1f}%"
    top_category = analysis.get("top_category") or "暂无"
    category_growth = trend.get("category_growth", {})
    comparable_growth = {name: value for name, value in category_growth.items() if value is not None}
    fastest_category = max(comparable_growth, key=comparable_growth.get, default=None)
    fastest_text = f"增长最快的类别是 **{fastest_category}**（{comparable_growth[fastest_category]:+.1f}%）。" if fastest_category else "当前缺少可比较的类别增长率。"
    priority_distribution = stats.get("priority_distribution", {})
    priority_text = "、".join(f"{name}优先级 {count} 条" for name, count in priority_distribution.items()) or "暂无"
    answer = f"""## 核心结论

筛选范围内共 **{total}** 条治理事件，主要类别为 **{top_category}**；{growth_text}。其中有 **{analysis.get('high_risk_count', 0)}** 条未完成高优先级事件。

## 数据依据

- 查询范围：{_filter_summary(plan)}
- 事件总数：{total}
- 风险分布：{priority_text}
- 平均处理时长：{stats.get('average_resolution_hours') if stats.get('average_resolution_hours') is not None else '暂无可计算数据'} 小时

{fastest_text}

## 建议

1. 优先复核未完成高优先级事件，明确责任人与处置时限。
2. 对数量较多或增长较快的类别继续按街道和时段下钻。
3. 原因属于待验证判断，需结合现场记录后再形成结论。"""
    if "证据" in query:
        incomplete = [row for row in state.get("cases", []) if not row.get("evidence_complete")]
        if incomplete:
            answer += f"\n\n## 待复核证据\n\n共有 **{len(incomplete)}** 条事件的结果证据尚不完整：\n\n{_format_case_table(incomplete, 10)}"
        else:
            answer += "\n\n当前筛选范围内没有标记为证据待补充的事件。"
    if sources:
        answer += "\n\n" + _knowledge_fallback(sources)
    answer += "\n\n## 信息来源\n\n- 治理事件数据库"
    return answer


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
    return str(content)


async def generate_response(state: AgentState) -> dict:
    fallback = _fallback_answer(state)
    answer = fallback
    response_reset = False
    plan = QueryPlan.model_validate(state["plan"])
    if plan.operation == "workflow":
        return {
            "final_answer": fallback,
            "suggestions": _suggested_questions(state),
            "execution_trace": [trace("generate_response", "生成执行回执", "已返回可验证的业务状态和处置轨迹")],
        }
    try:
        model = get_chat_model()
        if model is not None:
            history = [
                AIMessage(content=item["content"]) if item["role"] == "assistant" else HumanMessage(content=item["content"])
                for item in state.get("history", [])[-12:]
            ]
            if plan.operation == "refuse":
                return {"final_answer": fallback, "execution_trace": [trace("generate_response", "生成回答", "已按安全边界返回替代建议")]}
            if plan.operation == "chat":
                messages = [SystemMessage(content=SYSTEM_PROMPT), *history, HumanMessage(content=state["user_query"])]
            else:
                evidence = {
                    "question": state["user_query"], "plan": state["plan"],
                    "tool_results": state.get("tool_results", []), "cases": state.get("cases", [])[:50],
                    "knowledge": state.get("retrieved_context", []), "deterministic_draft": fallback,
                }
                messages = [
                    SystemMessage(content=SYSTEM_PROMPT), *history,
                    HumanMessage(content="请根据工具证据和确定性草稿直接回答本轮问题。不得新增证据中没有的数字、事件、规则或因果关系：\n" + json.dumps(evidence, ensure_ascii=False, default=str)),
                ]
            response = await model.ainvoke(messages)
            answer = _content_text(response.content).strip() or fallback
    except Exception as exc:
        logger.warning("LLM unavailable, returning grounded fallback: %s", exc)
        response_reset = True
    return {
        "final_answer": answer,
        "suggestions": _suggested_questions(state),
        "response_reset": response_reset,
        "execution_trace": [trace("generate_response", "生成回答", "已根据可验证数据与资料形成回答")],
    }


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("parse_request", parse_request)
    graph.add_node("knowledge_query", knowledge_query)
    graph.add_node("execute_plan", execute_plan)
    graph.add_node("analyse", analyse)
    graph.add_node("generate_response", generate_response)
    graph.add_edge(START, "parse_request")
    graph.add_conditional_edges("parse_request", choose_route, {
        "respond": "generate_response", "knowledge": "knowledge_query", "tools": "execute_plan",
    })
    graph.add_edge("knowledge_query", "analyse")
    graph.add_edge("execute_plan", "analyse")
    graph.add_edge("analyse", "generate_response")
    graph.add_edge("generate_response", END)
    return graph.compile()


agent_graph = build_graph()
