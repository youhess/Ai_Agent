from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from agent.model import get_chat_model


Intent = Literal["general_chat", "knowledge_query", "data_query", "analysis_query", "action_query", "unsafe"]
Operation = Literal[
    "chat", "list_cases", "case_detail", "aggregate", "compare_periods",
    "recurring_locations", "knowledge", "comprehensive", "workflow", "refuse",
]
GroupBy = Literal["district", "street", "category", "status", "level", "priority", "date"]
WorkflowAction = Literal["dispatch", "submit_result", "return_for_rework", "approve_close"]


class QueryFilters(BaseModel):
    district: str | None = Field(default=None, max_length=30)
    street: str | None = Field(default=None, max_length=30)
    category: str | None = Field(default=None, max_length=30)
    statuses: list[Literal["待处理", "处理中", "已完成"]] = Field(default_factory=list, max_length=3)
    level: Literal["一级", "二级", "三级"] | None = None
    priority: Literal["低", "中", "高"] | None = None
    days: int | None = Field(default=None, ge=1, le=3650)
    start_date: str | None = None
    end_date: str | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def valid_iso_datetime(cls, value: str | None) -> str | None:
        if value is not None:
            datetime.fromisoformat(value)
        return value


class QueryPlan(BaseModel):
    intent: Intent
    operation: Operation
    filters: QueryFilters = Field(default_factory=QueryFilters)
    case_id: str | None = Field(default=None, max_length=80)
    group_by: GroupBy | None = None
    limit: int = Field(default=20, ge=1, le=100)
    needs_knowledge: bool = False
    workflow_action: WorkflowAction | None = None
    responsible_unit: str | None = Field(default=None, max_length=40)
    collaborator_units: list[str] = Field(default_factory=list, max_length=8)
    evidence_complete: bool | None = None
    workflow_note: str | None = Field(default=None, max_length=300)
    confirmed: bool = False
    comparison_start_date: str | None = None
    comparison_end_date: str | None = None
    safety_reason: str | None = Field(default=None, max_length=200)

    @field_validator("comparison_start_date", "comparison_end_date")
    @classmethod
    def valid_comparison_datetime(cls, value: str | None) -> str | None:
        if value is not None:
            datetime.fromisoformat(value)
        return value


DISTRICTS = ["滨江区", "上城区", "拱墅区", "西湖区"]
STREETS = ["长河街道", "西兴街道", "浦沿街道", "湖滨街道", "望江街道", "四季青街道", "武林街道", "祥符街道", "半山街道", "翠苑街道", "古荡街道", "留下街道"]
CATEGORIES = ["市容环境", "垃圾堆放", "道路设施", "噪声扰民", "占道经营", "停车问题", "公共设施损坏", "社区服务"]
GOVERNANCE_UNITS = [
    "市容管理模拟组", "环卫处置模拟组", "道路养护模拟组", "综合协调模拟组",
    "交通协调模拟组", "设施维护模拟组", "社区服务模拟组", "社区网格模拟组",
    "物业协同模拟组",
]
CATEGORY_ALIASES = {
    "市容事件": "市容环境", "市容问题": "市容环境", "暴露垃圾": "垃圾堆放",
    "井盖": "公共设施损坏", "小广告": "市容环境", "乱贴小广告": "市容环境",
    "店外经营": "占道经营", "违停": "停车问题",
}

PLANNER_PROMPT = """你是治理数据查询规划器。请根据用户本轮问题和必要的对话历史输出一个 JSON 对象，不要输出解释。
字段：intent、operation、filters、case_id、group_by、limit、needs_knowledge、comparison_start_date、comparison_end_date。
intent 只能是 general_chat、knowledge_query、data_query、analysis_query、action_query、unsafe。
operation 只能是 chat、list_cases、case_detail、aggregate、compare_periods、recurring_locations、knowledge、comprehensive、workflow、refuse。
filters 可包含 district、street、category、statuses、level、priority、days、start_date、end_date。状态只能是待处理、处理中、已完成；level 只能是一级、二级、三级。
group_by 只能是 district、street、category、status、level、priority、date 或 null。
日期必须使用 ISO 8601。涉及数据但缺少可选筛选条件时不要臆造。问候和闲聊用 chat。危险操作、批量隐私披露、伪造法规文号或越权处罚用 refuse。"""


def _day_bounds(value: date) -> tuple[str, str]:
    return datetime.combine(value, time.min).isoformat(timespec="seconds"), datetime.combine(value, time.max).isoformat(timespec="seconds")


def _calendar_periods(query: str, today: date) -> tuple[dict[str, str], dict[str, str]]:
    current: dict[str, str] = {}
    previous: dict[str, str] = {}
    if "昨天" in query and "前天" in query:
        current["start_date"], current["end_date"] = _day_bounds(today - timedelta(days=1))
        previous["start_date"], previous["end_date"] = _day_bounds(today - timedelta(days=2))
    elif "今天" in query or "今日" in query:
        current["start_date"], current["end_date"] = _day_bounds(today)
    elif "昨天" in query:
        current["start_date"], current["end_date"] = _day_bounds(today - timedelta(days=1))
    elif "本周" in query:
        monday = today - timedelta(days=today.weekday())
        current["start_date"], current["end_date"] = _day_bounds(today)
        current["start_date"] = datetime.combine(monday, time.min).isoformat(timespec="seconds")
        previous_monday = monday - timedelta(days=7)
        previous["start_date"] = datetime.combine(previous_monday, time.min).isoformat(timespec="seconds")
        previous["end_date"] = datetime.combine(monday - timedelta(days=1), time.max).isoformat(timespec="seconds")
    elif "上周" in query:
        monday = today - timedelta(days=today.weekday())
        previous_monday = monday - timedelta(days=7)
        current["start_date"] = datetime.combine(previous_monday, time.min).isoformat(timespec="seconds")
        current["end_date"] = datetime.combine(monday - timedelta(days=1), time.max).isoformat(timespec="seconds")
    elif "本月" in query:
        month_start = today.replace(day=1)
        current["start_date"] = datetime.combine(month_start, time.min).isoformat(timespec="seconds")
        current["end_date"] = datetime.combine(today, time.max).isoformat(timespec="seconds")
        previous_end = month_start - timedelta(days=1)
        previous_start = previous_end.replace(day=1)
        previous["start_date"] = datetime.combine(previous_start, time.min).isoformat(timespec="seconds")
        previous["end_date"] = datetime.combine(previous_end, time.max).isoformat(timespec="seconds")
    return current, previous


def _explicit_date_range(query: str, today: date) -> dict[str, str]:
    match = re.search(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日?\s*(?:至|到|[-—~～])\s*(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日?", query)
    if not match:
        return {}
    start_year = int(match.group(1) or today.year)
    end_year = int(match.group(4) or start_year)
    start = date(start_year, int(match.group(2)), int(match.group(3)))
    end = date(end_year, int(match.group(5)), int(match.group(6)))
    start_value, _ = _day_bounds(start)
    _, end_value = _day_bounds(end)
    return {"start_date": start_value, "end_date": end_value}


def parse_filters(query: str, today: date | None = None) -> tuple[QueryFilters, dict[str, str]]:
    today = today or date.today()
    values: dict[str, Any] = {}
    for district in DISTRICTS:
        if district in query:
            values["district"] = district
            break
    if "district" not in values:
        match = re.search(r"([\u4e00-\u9fff]{2}(?<!社)区)", query)
        if match:
            values["district"] = match.group(1)
    for street in STREETS:
        if street in query:
            values["street"] = street
            break
    if "street" not in values:
        street_match = re.search(r"([\u4e00-\u9fff]{2}(?:街道|社区))", query)
        generic_locations = {"周各社区", "各个社区", "哪个社区", "每个社区", "所有社区", "全部社区", "多的社区", "少的社区", "当前社区"}
        if street_match and street_match.group(1) not in generic_locations:
            values["street"] = street_match.group(1)
    for category in CATEGORIES:
        if category in query:
            values["category"] = category
            break
    if "category" not in values:
        for alias, category in sorted(CATEGORY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if alias in query:
                values["category"] = category
                break
    if any(word in query for word in ["未办结", "没办结", "未完成", "没完成"]):
        values["statuses"] = ["待处理", "处理中"]
    elif "待处理" in query or "待处置" in query:
        values["statuses"] = ["待处理"]
    elif "处理中" in query or "处置中" in query:
        values["statuses"] = ["处理中"]
    elif any(word in query for word in ["已完成", "已办结", "办结的"]):
        values["statuses"] = ["已完成"]
    if "一级" in query:
        values["level"] = "一级"
    elif "二级" in query:
        values["level"] = "二级"
    elif "三级" in query:
        values["level"] = "三级"
    if "高风险" in query or "高优先级" in query:
        values["priority"] = "高"
    elif "中优先级" in query:
        values["priority"] = "中"
    elif "低优先级" in query:
        values["priority"] = "低"
    day_match = re.search(r"(?:最近|近|过去)\s*(\d+)\s*天", query)
    if day_match:
        values["days"] = min(int(day_match.group(1)), 3650)
    elif any(word in query for word in ["最近一周", "近一周", "过去一周"]):
        values["days"] = 7
    elif any(word in query for word in ["最近一个月", "近一个月", "过去一个月"]):
        values["days"] = 30
    current, previous = _calendar_periods(query, today)
    values.update(current)
    values.update(_explicit_date_range(query, today))
    return QueryFilters.model_validate(values), previous


def _unsafe_reason(query: str) -> str | None:
    if re.search(r"(?:导出|提供|列出).*(?:所有|全部).*(?:姓名|手机号|电话|住址|身份证)", query):
        return "不能批量披露个人身份与联系方式"
    if any(word in query for word in ["伪造法规", "真实文号", "处罚决定"]) or ("正式政府法规" in query and "Demo" in query):
        return "不能伪造政府文件、越权执法或生成处罚决定"
    if any(word in query for word in ["不明气体泄漏", "自己进去关闭阀门", "进入泄漏现场"]):
        return "不能提供可能导致人身危险的现场操作指令"
    return None


def _group_by(query: str) -> GroupBy | None:
    if any(word in query for word in ["各区", "哪个区", "按区"]):
        return "district"
    if any(word in query for word in ["各社区", "哪个社区", "按社区", "最多的社区", "各街道", "哪个街道", "按街道", "点位"]):
        return "street"
    if any(word in query for word in ["各类", "类别", "类型", "哪类"]):
        return "category"
    if "状态" in query:
        return "status"
    if any(word in query for word in ["等级", "优先级", "风险分布"]):
        return "level" if "等级" in query else "priority"
    if any(word in query for word in ["每日", "每天", "按日"]):
        return "date"
    return None


def _previous_user_query(history: list[dict[str, str]]) -> str | None:
    for item in reversed(history):
        if item.get("role") == "user" and item.get("content", "").strip():
            return item["content"].strip()
    return None


def _workflow_request(query: str, case_id: str | None) -> dict[str, Any] | None:
    if not case_id:
        return None
    action: WorkflowAction | None = None
    if any(word in query for word in ["退回补充", "退回整改", "退回重办", "复核退回"]):
        action = "return_for_rework"
    elif any(word in query for word in ["复核办结", "确认办结", "批准办结", "办结归档"]):
        action = "approve_close"
    elif any(word in query for word in ["提交处置结果", "提交处理结果", "上传处置证据", "提交现场反馈"]):
        action = "submit_result"
    elif (
        any(word in query for word in ["确认协同派单", "执行协同派单", "确认派单", "执行派单", "分派至", "派给"])
        or ("协同派单" in query and not any(word in query for word in ["建议", "方案", "分析", "研判", "如何"]))
    ):
        action = "dispatch"
    if action is None:
        return None

    primary_text = query.split("协办", 1)[0]
    primary_unit = next((unit for unit in GOVERNANCE_UNITS if unit in primary_text), None)
    collaborators: list[str] = []
    if "协办" in query:
        collaborator_text = query.split("协办", 1)[1]
        collaborators = [unit for unit in GOVERNANCE_UNITS if unit in collaborator_text and unit != primary_unit]
    evidence_complete: bool | None = None
    if any(word in query for word in ["证据完整", "证据齐全", "材料完整", "材料齐全"]):
        evidence_complete = True
    elif any(word in query for word in ["证据不足", "证据不全", "材料待补充", "证据待补充"]):
        evidence_complete = False
    note_match = re.search(r"(?:备注|说明)[：:]\s*(.{1,300})$", query)
    return {
        "workflow_action": action,
        "responsible_unit": primary_unit,
        "collaborator_units": collaborators,
        "evidence_complete": evidence_complete,
        "workflow_note": note_match.group(1).strip() if note_match else None,
        "confirmed": (
            any(word in query for word in ["确认", "执行", "立即", "马上"])
            and not any(word in query for word in ["不要", "暂不", "先不", "不确认", "取消"])
        ),
    }


def build_deterministic_plan(query: str, history: list[dict[str, str]] | None = None, today: date | None = None) -> QueryPlan:
    history = history or []
    reason = _unsafe_reason(query)
    if reason:
        return QueryPlan(intent="unsafe", operation="refuse", safety_reason=reason)
    filters, comparison = parse_filters(query, today)
    case_match = re.search(r"\b(?:SG|DEMO)-[A-Z0-9-]{4,}\b", query, re.IGNORECASE)
    case_id = case_match.group(0).upper() if case_match else None
    workflow = _workflow_request(query, case_id)
    knowledge_words = ["规范", "规定", "指南", "如何处置", "如何处理", "怎么处理", "流程", "分级规则", "办结要求", "证据", "如何判断", "冲突", "知识库", "条款", "Demo知识", "处置建议", "派单建议", "派单方案", "协同方案", "主办单位", "协办单位"]
    data_action_words = ["查询", "统计", "列出", "找出", "汇总", "对比", "趋势", "增长", "分布", "排名", "事件量", "数量"]
    aggregate_words = ["统计", "多少", "占比", "分布", "排名", "最多", "汇总", "增长最快"]
    data_words = [*data_action_words, "高风险", "待处理", "完成率", "点位"]
    analysis_words = ["分析", "异常", "建议", "原因", "为什么", "关注", "优先跟进", "对比", "相比"]
    wants_knowledge = any(word in query for word in knowledge_words)
    wants_data = any(word in query for word in data_words) or case_id is not None
    wants_analysis = any(word in query for word in analysis_words)
    group_by = _group_by(query)
    if workflow:
        operation: Operation = "workflow"
    elif case_id:
        operation: Operation = "case_detail"
    elif any(word in query for word in ["反复", "重复发生", "至少三次", "频繁点位"]):
        operation = "recurring_locations"
    elif any(word in query for word in ["对比", "相比", "较上周", "比上周", "环比"]) or ("昨天" in query and "前天" in query) or re.search(r"比.+(?:多|少|高|低)", query):
        operation = "compare_periods"
    elif wants_knowledge and (wants_analysis or any(word in query for word in data_action_words)):
        operation = "comprehensive"
    elif wants_knowledge:
        operation = "knowledge"
    elif wants_analysis:
        operation = "comprehensive"
    elif any(word in query for word in aggregate_words):
        operation = "aggregate"
    elif wants_data:
        operation = "list_cases"
    else:
        operation = "chat"
    if operation == "chat" and re.search(r"^(那|那么|换成|改成|再看|也看)", query):
        previous_query = _previous_user_query(history)
        if previous_query:
            previous_plan = build_deterministic_plan(previous_query, [], today)
            previous_values = previous_plan.filters.model_dump()
            current_values = filters.model_dump()
            merged = {key: current_values[key] if current_values[key] not in (None, []) else value for key, value in previous_values.items()}
            filters = QueryFilters.model_validate(merged)
            operation = previous_plan.operation
            group_by = previous_plan.group_by
            wants_knowledge = previous_plan.needs_knowledge
    intent: Intent
    if operation == "chat":
        intent = "general_chat"
    elif operation == "workflow":
        intent = "action_query"
    elif operation == "knowledge":
        intent = "knowledge_query"
    elif operation in {"comprehensive", "compare_periods", "recurring_locations"} or wants_analysis:
        intent = "analysis_query"
    else:
        intent = "data_query"
    limit_match = re.search(r"(?:前|最多|列出)\s*([一二三四五六七八九十\d]+)\s*条", query)
    chinese_numbers = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if limit_match:
        raw_limit = limit_match.group(1)
        parsed_limit = int(raw_limit) if raw_limit.isdigit() else chinese_numbers.get(raw_limit, 20)
        limit = min(parsed_limit, 100)
    else:
        limit = 20
    return QueryPlan(
        intent=intent,
        operation=operation,
        filters=filters,
        case_id=case_id,
        group_by=group_by,
        limit=limit,
        needs_knowledge=wants_knowledge,
        workflow_action=workflow.get("workflow_action") if workflow else None,
        responsible_unit=workflow.get("responsible_unit") if workflow else None,
        collaborator_units=workflow.get("collaborator_units", []) if workflow else [],
        evidence_complete=workflow.get("evidence_complete") if workflow else None,
        workflow_note=workflow.get("workflow_note") if workflow else None,
        confirmed=bool(workflow and workflow.get("confirmed")),
        comparison_start_date=comparison.get("start_date"),
        comparison_end_date=comparison.get("end_date"),
    )


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
    return str(content)


def _extract_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    if start < 0:
        raise ValueError("规划结果不包含 JSON")
    value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError("规划结果不是 JSON 对象")
    return value


async def plan_query(query: str, history: list[dict[str, str]] | None = None) -> QueryPlan:
    history = history or []
    deterministic = build_deterministic_plan(query, history)
    try:
        model = get_chat_model()
    except Exception:
        return deterministic
    if model is None or deterministic.operation in {"chat", "workflow", "refuse"}:
        return deterministic
    context = {"history": history[-6:], "question": query, "today": date.today().isoformat(), "deterministic_draft": deterministic.model_dump()}
    try:
        response = await model.ainvoke([
            SystemMessage(content=PLANNER_PROMPT),
            HumanMessage(content=json.dumps(context, ensure_ascii=False)),
        ])
        planned = QueryPlan.model_validate(_extract_json(_content_text(response.content)))
        if deterministic.case_id and not planned.case_id:
            planned.case_id = deterministic.case_id
            planned.operation = "case_detail"
        return planned
    except Exception:
        return deterministic
