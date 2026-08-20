import httpx
import pytest

from config import get_settings
from rag.retriever import reset_retrieval_runtime_state, retrieval_status, retrieve
from rag.xingchen import normalize_xingchen_response


@pytest.fixture
def remote_rag_environment(monkeypatch):
    monkeypatch.setenv("RAG_PROVIDER", "auto")
    monkeypatch.setenv("XINGCHEN_RAG_API_URL", "https://example.invalid/rag-workflow")
    monkeypatch.setenv("XINGCHEN_RAG_API_KEY", "test-secret-never-serialize")
    monkeypatch.setenv("XINGCHEN_RAG_REQUEST_STYLE", "workflow")
    monkeypatch.setenv("XINGCHEN_RAG_QUERY_FIELD", "query")
    monkeypatch.setenv("XINGCHEN_RAG_CONTEXT_FIELD", "case_context")
    get_settings.cache_clear()
    reset_retrieval_runtime_state()
    yield
    get_settings.cache_clear()
    reset_retrieval_runtime_state()


class _FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "data": {
                "outputs": {
                    "answer": "高风险事件应先分级，再由主办单位联动处置。",
                    "sources": [
                        {"title": "协同处置规则", "content": "形成主办、协办和复核闭环。", "score": 0.92},
                    ],
                },
            },
        }


def test_xingchen_rag_success_uses_workflow_payload(monkeypatch, remote_rag_environment):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return _FakeResponse()

    monkeypatch.setattr("rag.xingchen.httpx.post", fake_post)
    results = retrieve(
        "高风险事件如何处置？",
        limit=4,
        context={"id": "SG-DEMO-0001", "level": "高风险"},
    )

    assert results[0]["result_type"] == "answer"
    assert all(item["retrieval_mode"] == "xingchen" for item in results)
    assert captured["headers"]["Authorization"] == "Bearer test-secret-never-serialize"
    assert captured["json"]["inputs"]["query"] == "高风险事件如何处置？"
    assert '"id": "SG-DEMO-0001"' in captured["json"]["inputs"]["case_context"]
    status = retrieval_status()
    assert status["last_provider"] == "xingchen"
    assert status["fallback_count"] == 0
    assert "test-secret" not in str(status)


def test_xingchen_failure_falls_back_to_local_index(monkeypatch, remote_rag_environment):
    def fail_post(url, **kwargs):
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr("rag.xingchen.httpx.post", fail_post)
    results = retrieve("高风险事件应该如何分级处置", limit=4)

    assert results
    assert all(item["retrieval_mode"] != "xingchen" for item in results)
    status = retrieval_status()
    assert status["last_provider"] == "local_fallback"
    assert status["fallback_count"] == 1
    assert status["last_error"] == "星辰 RAG API 连接或响应解析失败"
    assert "offline" not in str(status)


def test_local_mode_never_calls_remote(monkeypatch):
    monkeypatch.setenv("RAG_PROVIDER", "local")
    monkeypatch.setenv("XINGCHEN_RAG_API_URL", "https://example.invalid/rag-workflow")
    monkeypatch.setenv("XINGCHEN_RAG_API_KEY", "unused-secret")
    get_settings.cache_clear()
    reset_retrieval_runtime_state()
    monkeypatch.setattr(
        "rag.xingchen.httpx.post",
        lambda *args, **kwargs: pytest.fail("local mode must not call Xingchen"),
    )

    assert retrieve("治理事件办结证据", limit=2)
    status = retrieval_status()
    assert status["last_provider"] == "local"
    assert status["fallback_count"] == 0
    get_settings.cache_clear()
    reset_retrieval_runtime_state()


def test_normalizer_accepts_flat_and_openai_compatible_outputs():
    flat = normalize_xingchen_response(
        {"answer": "工作流答案", "retrieval_results": [{"name": "规则A", "chunk": "片段A"}]},
        4,
    )
    openai = normalize_xingchen_response(
        {"choices": [{"message": {"content": "兼容回答"}}]},
        4,
    )

    assert [item["document_name"] for item in flat] == ["星辰 RAG 工作流回答", "规则A"]
    assert openai[0]["chunk"] == "兼容回答"
