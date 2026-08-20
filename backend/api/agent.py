import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent.graph import agent_graph
from database.admin_repository import (
    append_agent_run_step,
    create_agent_run,
    finish_agent_run,
    update_agent_run_intent,
)
from schemas.agent import AgentRequest

router = APIRouter(prefix="/api/agent", tags=["agent"])
logger = logging.getLogger(__name__)


def event(event_type: str, data=None) -> str:
    payload = {"type": event_type}
    if data is not None:
        payload["data"] = data
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
    return str(content or "")


@router.post("/stream")
async def stream_agent(request: AgentRequest):
    run_id = uuid.uuid4().hex
    create_agent_run(run_id, request.message)

    async def generate():
        started = time.perf_counter()
        answer = ""
        tools: list[str] = []
        sources: list[dict] = []
        step_position = 0
        try:
            yield event("run", {"run_id": run_id, "status": "running"})
            initial = {
                "user_query": request.message,
                "history": [item.model_dump() for item in request.history],
                "tool_results": [],
                "retrieved_context": [],
                "execution_trace": [],
            }
            simple_response = False
            streamed_answer = False
            async for mode, update in agent_graph.astream(initial, stream_mode=["updates", "messages"]):
                if mode == "messages":
                    message, metadata = update
                    if metadata.get("langgraph_node") == "generate_response":
                        content = message_text(message.content)
                        if content:
                            streamed_answer = True
                            answer += content
                            yield event("answer", {"content": content, "delta": True})
                    continue
                for node_name, node_update in update.items():
                    if node_name == "parse_request":
                        simple_response = node_update.get("plan", {}).get("operation") in {"chat", "refuse"}
                        update_agent_run_intent(run_id, node_update.get("intent"))
                    for item in node_update.get("execution_trace", []):
                        step_position += 1
                        append_agent_run_step(run_id, item, step_position)
                        if not simple_response:
                            yield event("trace", item)
                    for source in node_update.get("retrieved_context", []):
                        sources.append(source)
                        yield event("source", source)
                    for tool_result in node_update.get("tool_results", []):
                        tool_name = str(tool_result.get("tool", ""))
                        if tool_name and tool_name not in tools:
                            tools.append(tool_name)
                    if node_update.get("final_answer"):
                        if not streamed_answer or node_update.get("response_reset"):
                            answer = node_update["final_answer"]
                            yield event("answer", {
                                "content": node_update["final_answer"],
                                "reset": bool(streamed_answer and node_update.get("response_reset")),
                            })
                    if node_update.get("suggestions"):
                        yield event("suggestions", node_update["suggestions"])
                await asyncio.sleep(0)
            duration_ms = round((time.perf_counter() - started) * 1000)
            finish_agent_run(
                run_id, status="completed", answer=answer, duration_ms=duration_ms,
                tools=tools, sources=sources,
            )
            yield event("done", {"run_id": run_id, "status": "completed", "duration_ms": duration_ms})
        except asyncio.CancelledError:
            logger.info("SSE client disconnected")
            finish_agent_run(
                run_id, status="cancelled", answer=answer,
                duration_ms=round((time.perf_counter() - started) * 1000), tools=tools, sources=sources,
            )
        except Exception as exc:
            logger.exception("Agent execution failed")
            duration_ms = round((time.perf_counter() - started) * 1000)
            finish_agent_run(
                run_id, status="failed", answer=answer, error_code=type(exc).__name__,
                duration_ms=duration_ms, tools=tools, sources=sources,
            )
            yield event("error", {"message": "智能分析暂时不可用，请检查数据与模型配置后重试。", "code": type(exc).__name__})
            yield event("done", {"run_id": run_id, "status": "failed", "duration_ms": duration_ms})
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
