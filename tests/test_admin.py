import json
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from database.admin_repository import create_agent_run, finish_agent_run, replace_cases_from_import
from database.repository import query_cases, replace_cases
from main import app
from rag.vector_store import LocalVectorStore
from scripts.generate_sample_data import generate


def _events(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_admin_config_is_read_only_and_never_exposes_secrets():
    with TestClient(app) as client:
        response = client.get("/api/admin/agent/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["editable"] is False
    assert len(payload["tools"]) == 11
    assert any(item["name"] == "recommend_case_collaboration" for item in payload["tools"])
    assert any(item["name"] == "advance_case_workflow" for item in payload["tools"])
    serialized = json.dumps(payload).lower()
    assert "api_key" not in serialized
    assert "system_prompt" not in serialized


def test_dataset_csv_preview_commit_and_defaults():
    csv_bytes = (
        "事件ID,区域,类型,事件描述,上报时间\n"
        "IMPORT-001,滨江区,道路设施,道路破损,2026-08-19 09:00:00\n"
        "IMPORT-002,西湖区,社区服务,便民服务咨询,2026-08-19 10:00:00\n"
    ).encode("utf-8-sig")
    try:
        with TestClient(app) as client:
            preview = client.post(
                "/api/admin/data/imports/preview",
                files={"file": ("events.csv", csv_bytes, "text/csv")},
            )
            assert preview.status_code == 200
            result = preview.json()
            assert result["can_commit"] is True
            assert result["row_count"] == 2
            assert result["preview"][0]["street"] == "未提供"
            assert result["preview"][0]["priority"] == "中"
            committed = client.post(f"/api/admin/data/imports/{result['import_id']}/commit")
            assert committed.status_code == 200
            assert client.get("/api/admin/data/summary").json()["record_count"] == 2
            rows = client.get("/api/admin/data/rows", params={"page": 1, "page_size": 20}).json()
            assert {item["id"] for item in rows["items"]} == {"IMPORT-001", "IMPORT-002"}
    finally:
        replace_cases(generate())


def test_dataset_preview_rejects_duplicate_ids_and_invalid_values():
    csv_bytes = (
        "事件ID,区域,类型,事件描述,上报时间,状态\n"
        "BAD-001,滨江区,道路设施,道路破损,not-a-date,未知\n"
        "BAD-001,滨江区,道路设施,重复事件,2026-08-19,待处理\n"
    ).encode("utf-8")
    with TestClient(app) as client:
        response = client.post(
            "/api/admin/data/imports/preview",
            files={"file": ("bad.csv", csv_bytes, "text/csv")},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["can_commit"] is False
    assert payload["error_count"] >= 3


def test_downloaded_xlsx_template_can_be_previewed():
    with TestClient(app) as client:
        template = client.get("/api/admin/data/template")
        assert template.status_code == 200
        assert "spreadsheetml" in template.headers["content-type"]
        preview = client.post(
            "/api/admin/data/imports/preview",
            files={"file": ("template.xlsx", template.content, template.headers["content-type"])},
        )
    assert preview.status_code == 200
    assert preview.json()["can_commit"] is True


def test_failed_dataset_transaction_keeps_existing_rows():
    original_count = len(query_cases(limit=1000))
    invalid = {
        "id": "INVALID-001", "category": "道路设施", "district": "滨江区", "street": "未提供",
        "description": "非法状态测试", "level": "三级", "priority": "中", "status": "非法状态",
        "responsible_unit": "待分派单位", "evidence_complete": 0,
        "created_at": "2026-08-19T09:00:00", "resolved_at": None, "source": "测试",
    }
    with pytest.raises(sqlite3.IntegrityError):
        replace_cases_from_import("missing-import", [invalid])
    assert len(query_cases(limit=1000)) == original_count


def test_knowledge_upload_duplicate_protection_and_delete():
    content = f"测试治理规范 {uuid.uuid4().hex}\n高风险事件应先核验再分派。".encode("utf-8")
    with TestClient(app) as client:
        uploaded = client.post(
            "/api/admin/knowledge/documents",
            files={"file": ("测试规范.md", content, "text/markdown")},
        )
        assert uploaded.status_code == 201
        result = uploaded.json()
        assert result["document"]["status"] == "indexed"
        assert result["document"]["source_type"] == "uploaded"
        duplicate = client.post(
            "/api/admin/knowledge/documents",
            files={"file": ("重复资料.md", content, "text/markdown")},
        )
        assert duplicate.status_code == 422
        documents = client.get("/api/admin/knowledge/documents").json()["items"]
        built_in = next(item for item in documents if item["source_type"] == "built_in")
        assert client.delete(f"/api/admin/knowledge/documents/{built_in['id']}").status_code == 409
        removed = client.delete(f"/api/admin/knowledge/documents/{result['document']['id']}")
        assert removed.status_code == 200


def test_hybrid_vector_search_and_lexical_fallback(tmp_path):
    store = LocalVectorStore(tmp_path / "index.json")
    documents = [
        {"document_name": "道路规范.md", "chunk": "道路设施破损处置流程", "chunk_id": "1"},
        {"document_name": "噪声规范.md", "chunk": "夜间噪声扰民处置流程", "chunk_id": "2"},
    ]
    assert store.build(documents, [[1.0, 0.0], [0.0, 1.0]]) == "hybrid"
    hybrid = LocalVectorStore(tmp_path / "index.json").search("完全无关词", query_embedding=[1.0, 0.0], min_score=0)
    assert hybrid[0]["document_name"] == "道路规范.md"
    assert hybrid[0]["retrieval_mode"] == "hybrid"
    lexical = LocalVectorStore(tmp_path / "index.json").search("夜间噪声", min_score=0)
    assert lexical[0]["document_name"] == "噪声规范.md"
    assert lexical[0]["retrieval_mode"] == "lexical"


def test_agent_stream_persists_completed_run_and_trace():
    with TestClient(app) as client:
        response = client.post("/api/agent/stream", json={"message": "滨江区最近7天有多少治理事件？"})
        events = _events(response.text)
        run_id = next(item["data"]["run_id"] for item in events if item["type"] == "run")
        done = next(item["data"] for item in events if item["type"] == "done")
        detail = client.get(f"/api/admin/runs/{run_id}").json()
    assert done["status"] == "completed"
    assert detail["status"] == "completed"
    assert detail["answer"]
    assert detail["steps"]
    assert detail["tools"]


def test_agent_failure_and_cancelled_status_are_queryable(monkeypatch):
    class BrokenGraph:
        async def astream(self, *_args, **_kwargs):
            raise RuntimeError("test failure")
            yield  # pragma: no cover

    monkeypatch.setattr("api.agent.agent_graph", BrokenGraph())
    with TestClient(app) as client:
        response = client.post("/api/agent/stream", json={"message": "触发测试异常"})
        events = _events(response.text)
        failed_id = next(item["data"]["run_id"] for item in events if item["type"] == "run")
        assert client.get(f"/api/admin/runs/{failed_id}").json()["status"] == "failed"

        cancelled_id = uuid.uuid4().hex
        create_agent_run(cancelled_id, "取消状态测试")
        finish_agent_run(cancelled_id, status="cancelled", duration_ms=10)
        cancelled = client.get("/api/admin/runs", params={"status": "cancelled"}).json()
        assert any(item["id"] == cancelled_id for item in cancelled["items"])
