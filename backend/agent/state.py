import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict, total=False):
    user_query: str
    history: list[dict[str, str]]
    plan: dict[str, Any]
    intent: str
    entities: dict[str, Any]
    cases: list[dict[str, Any]]
    tool_results: Annotated[list[dict[str, Any]], operator.add]
    retrieved_context: Annotated[list[dict[str, Any]], operator.add]
    analysis_result: dict[str, Any]
    final_answer: str
    response_reset: bool
    execution_trace: Annotated[list[dict[str, Any]], operator.add]
