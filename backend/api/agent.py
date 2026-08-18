import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent.graph import agent_graph
from schemas.agent import AgentRequest

router = APIRouter(prefix="/api/agent", tags=["agent"])
logger = logging.getLogger(__name__)


def event(event_type: str, data=None) -> str:
    payload = {"type": event_type}
    if data is not None:
        payload["data"] = data
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@router.post("/stream")
async def stream_agent(request: AgentRequest):
    async def generate():
        try:
            initial = {"user_query": request.message, "tool_results": [], "retrieved_context": [], "execution_trace": []}
            async for update in agent_graph.astream(initial, stream_mode="updates"):
                for node_update in update.values():
                    for item in node_update.get("execution_trace", []):
                        yield event("trace", item)
                    for source in node_update.get("retrieved_context", []):
                        yield event("source", source)
                    if node_update.get("final_answer"):
                        yield event("answer", {"content": node_update["final_answer"]})
                await asyncio.sleep(0)
            yield event("done")
        except asyncio.CancelledError:
            logger.info("SSE client disconnected")
        except Exception as exc:
            logger.exception("Agent execution failed")
            yield event("error", {"message": "智能分析暂时不可用，请检查数据与模型配置后重试。", "code": type(exc).__name__})
            yield event("done")
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
