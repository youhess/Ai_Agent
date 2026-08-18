import re
from datetime import datetime


DISTRICTS = ["滨江区", "上城区", "拱墅区", "西湖区"]
CATEGORIES = ["市容环境", "垃圾堆放", "道路设施", "噪声扰民", "占道经营", "停车问题", "公共设施损坏", "社区服务"]


def parse_query(query: str) -> dict:
    entities: dict = {}
    for district in DISTRICTS:
        if district in query:
            entities["district"] = district
    for category in CATEGORIES:
        if category in query:
            entities["category"] = category
    day_match = re.search(r"(?:最近|近)(\d+)天", query)
    if day_match:
        entities["days"] = min(int(day_match.group(1)), 3650)
    elif "最近一周" in query or "近一周" in query or "本周" in query:
        entities["days"] = 7
    elif "最近一个月" in query or "近一个月" in query or "本月" in query:
        entities["days"] = 30
    elif "今天" in query or "今日" in query:
        entities["days"] = 1
    for status in ["待处理", "处理中", "已完成"]:
        if status in query:
            entities["status"] = status
    if "高风险" in query or "高优先级" in query:
        entities["priority"] = "高"
    entities["parsed_at"] = datetime.now().isoformat(timespec="seconds")
    return entities


def route_query(query: str) -> str:
    lower = query.lower()
    knowledge_words = ["规范", "规定", "指南", "如何处置", "如何处理", "怎么处理", "流程", "分级规则"]
    data_words = ["多少", "事件", "统计", "趋势", "增长", "高风险", "待处理", "完成率", "哪个区域", "类别"]
    analysis_words = ["分析", "异常", "建议", "治理情况"]
    wants_knowledge = any(word in lower for word in knowledge_words)
    wants_data = any(word in lower for word in data_words)
    wants_analysis = any(word in lower for word in analysis_words)
    if wants_knowledge and (wants_analysis or any(word in lower for word in ["多少", "统计", "趋势", "增长", "数据", "结合"])):
        return "analysis_query"
    if wants_knowledge:
        return "knowledge_query"
    if wants_data or wants_analysis:
        return "analysis_query" if wants_analysis else "data_query"
    return "general_chat"
