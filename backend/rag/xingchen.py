from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx

from config import get_settings


class XingchenRagError(RuntimeError):
    """A safe, user-displayable error raised by the remote RAG adapter."""


def xingchen_configured() -> bool:
    settings = get_settings()
    return bool(settings.xingchen_rag_api_url.strip() and settings.xingchen_rag_api_key.strip())


def _validate_endpoint(url: str) -> str:
    endpoint = url.strip()
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise XingchenRagError("星辰 RAG API 地址格式不正确")
    return endpoint


def _request_payload(query: str, limit: int, context: dict[str, Any] | None) -> dict[str, Any]:
    settings = get_settings()
    style = settings.xingchen_rag_request_style.strip().lower()
    context_value = json.dumps(context, ensure_ascii=False, default=str) if context else ""
    if style == "flat":
        payload: dict[str, Any] = {
            settings.xingchen_rag_query_field: query,
            "limit": limit,
        }
        if context_value and settings.xingchen_rag_context_field:
            payload[settings.xingchen_rag_context_field] = context_value
        return payload
    if style != "workflow":
        raise XingchenRagError("XINGCHEN_RAG_REQUEST_STYLE 仅支持 workflow 或 flat")
    inputs: dict[str, Any] = {settings.xingchen_rag_query_field: query}
    if context_value and settings.xingchen_rag_context_field:
        inputs[settings.xingchen_rag_context_field] = context_value
    return {
        "inputs": inputs,
        "response_mode": "blocking",
        "user": settings.xingchen_rag_user_id,
    }


def _nested_output(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    value: Any = payload
    for key in ("data", "outputs"):
        if isinstance(value, dict) and key in value:
            value = value[key]
    return value


def _find_value(payload: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload and payload[key] not in (None, "", []):
                return payload[key]
        for value in payload.values():
            found = _find_value(value, keys)
            if found not in (None, "", []):
                return found
    return None


def _text_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_text_value(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        for key in ("content", "text", "chunk", "page_content", "answer", "output"):
            if key in value:
                return _text_value(value[key])
    return ""


def _source_item(item: Any, index: int) -> dict[str, Any] | None:
    if isinstance(item, str):
        content = item.strip()
        return {
            "document_name": f"星辰知识片段 {index + 1}", "chunk": content,
            "score": 1.0, "retrieval_mode": "xingchen", "provider": "xingchen",
        } if content else None
    if not isinstance(item, dict):
        return None
    segment = item.get("segment") if isinstance(item.get("segment"), dict) else {}
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    content = _text_value(item) or _text_value(segment)
    if not content:
        return None
    title = (
        item.get("document_name") or item.get("title") or item.get("name")
        or segment.get("document_name") or segment.get("title")
        or metadata.get("document_name") or metadata.get("title") or metadata.get("filename")
        or f"星辰知识片段 {index + 1}"
    )
    raw_score = item.get("score", item.get("relevance_score", segment.get("score", 1.0)))
    try:
        score = round(float(raw_score), 4)
    except (TypeError, ValueError):
        score = 1.0
    result = {
        "document_name": str(title), "chunk": content, "score": score,
        "retrieval_mode": "xingchen", "provider": "xingchen",
    }
    url = item.get("url") or item.get("link") or metadata.get("url")
    if url:
        result["url"] = str(url)
    return result


def normalize_xingchen_response(payload: Any, limit: int) -> list[dict[str, Any]]:
    output = _nested_output(payload)
    source_value = _find_value(output, ("sources", "citations", "documents", "retrieval_results", "records"))
    if source_value is None:
        possible_result = _find_value(output, ("result",))
        source_value = possible_result if isinstance(possible_result, list) else None
    raw_sources = source_value if isinstance(source_value, list) else []
    sources = [normalized for index, item in enumerate(raw_sources) if (normalized := _source_item(item, index))]

    answer_value = _find_value(output, ("answer", "output", "text"))
    if answer_value is None:
        result_value = _find_value(output, ("result",))
        answer_value = result_value if isinstance(result_value, str) else None
    if answer_value is None and isinstance(payload, dict):
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            answer_value = choices[0].get("message", {}).get("content") if isinstance(choices[0], dict) else None
    answer = _text_value(answer_value)
    if answer:
        sources.insert(0, {
            "document_name": "星辰 RAG 工作流回答", "chunk": answer, "score": 1.0,
            "retrieval_mode": "xingchen", "provider": "xingchen", "result_type": "answer",
        })
    return sources[: max(1, limit)]


def retrieve_from_xingchen(
    query: str, limit: int = 4, context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    if not xingchen_configured():
        raise XingchenRagError("星辰 RAG API 尚未配置")
    endpoint = _validate_endpoint(settings.xingchen_rag_api_url)
    max_chars = max(1, min(settings.xingchen_rag_max_query_chars, 4000))
    remote_query = query[:max_chars]
    headers = {
        "Authorization": f"Bearer {settings.xingchen_rag_api_key.strip()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "grassroots-governance-agent/1.0",
    }
    try:
        response = httpx.post(
            endpoint,
            headers=headers,
            json=_request_payload(remote_query, limit, context),
            timeout=max(1, settings.xingchen_rag_timeout),
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise XingchenRagError("星辰 RAG API 调用超时") from exc
    except httpx.HTTPStatusError as exc:
        raise XingchenRagError(f"星辰 RAG API 返回 HTTP {exc.response.status_code}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise XingchenRagError("星辰 RAG API 连接或响应解析失败") from exc
    return normalize_xingchen_response(payload, limit)
