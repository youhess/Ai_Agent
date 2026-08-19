from langchain_core.tools import BaseTool

from agent.tools.analytics_tools import (
    aggregate_cases,
    analyse_case_trend,
    compare_case_periods,
    find_recurring_locations,
    get_case_statistics,
    get_high_risk_cases,
)
from agent.tools.case_tools import get_case_detail, query_cases
from agent.tools.knowledge_tools import search_knowledge_base


TOOL_REGISTRY: dict[str, BaseTool] = {}


def register_tools(tools: list[BaseTool]) -> None:
    for registered_tool in tools:
        TOOL_REGISTRY[registered_tool.name] = registered_tool


register_tools([
    query_cases, get_case_statistics, analyse_case_trend, get_high_risk_cases,
    aggregate_cases, compare_case_periods, find_recurring_locations,
    get_case_detail, search_knowledge_base,
])


def get_tools() -> list[BaseTool]:
    return list(TOOL_REGISTRY.values())
