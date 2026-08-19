from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from database.connection import database


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def upsert_knowledge_document(document: dict[str, Any]) -> None:
    timestamp = now_iso()
    with database() as connection:
        existing = connection.execute(
            "SELECT id, created_at FROM knowledge_documents WHERE id = ? OR sha256 = ?",
            (document["id"], document["sha256"]),
        ).fetchone()
        document_id = existing["id"] if existing else document["id"]
        created_at = existing["created_at"] if existing else timestamp
        connection.execute(
            """
            INSERT INTO knowledge_documents (
                id, file_name, stored_name, source_type, sha256, size_bytes, status,
                chunk_count, index_mode, error_message, created_at, updated_at, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                file_name=excluded.file_name, stored_name=excluded.stored_name,
                source_type=excluded.source_type, sha256=excluded.sha256,
                size_bytes=excluded.size_bytes, updated_at=excluded.updated_at
            """,
            (
                document_id, document["file_name"], document.get("stored_name"), document["source_type"],
                document["sha256"], document["size_bytes"], document.get("status", "pending"),
                document.get("chunk_count", 0), document.get("index_mode", "lexical"),
                document.get("error_message"), created_at, timestamp, document.get("indexed_at"),
            ),
        )


def get_knowledge_document(document_id: str) -> dict[str, Any] | None:
    with database() as connection:
        row = connection.execute("SELECT * FROM knowledge_documents WHERE id = ?", (document_id,)).fetchone()
        return dict(row) if row else None


def find_knowledge_by_sha256(sha256: str) -> dict[str, Any] | None:
    with database() as connection:
        row = connection.execute("SELECT * FROM knowledge_documents WHERE sha256 = ?", (sha256,)).fetchone()
        return dict(row) if row else None


def list_knowledge_documents() -> list[dict[str, Any]]:
    with database() as connection:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM knowledge_documents ORDER BY source_type, created_at DESC, file_name"
        ).fetchall()]


def update_knowledge_status(
    document_id: str, *, status: str, chunk_count: int = 0, index_mode: str = "lexical",
    error_message: str | None = None, indexed: bool = False,
) -> None:
    timestamp = now_iso()
    with database() as connection:
        connection.execute(
            """UPDATE knowledge_documents
               SET status = ?, chunk_count = ?, index_mode = ?, error_message = ?,
                   updated_at = ?, indexed_at = CASE WHEN ? THEN ? ELSE indexed_at END
               WHERE id = ?""",
            (status, chunk_count, index_mode, error_message, timestamp, int(indexed), timestamp, document_id),
        )


def delete_knowledge_document(document_id: str) -> None:
    with database() as connection:
        connection.execute("DELETE FROM knowledge_documents WHERE id = ?", (document_id,))


def create_dataset_import(record: dict[str, Any]) -> None:
    with database() as connection:
        connection.execute(
            """INSERT INTO dataset_imports
               (id, file_name, stored_path, size_bytes, status, row_count, error_count,
                errors_json, warnings_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["id"], record["file_name"], record["stored_path"], record["size_bytes"],
                record["status"], record["row_count"], record["error_count"],
                _json(record.get("errors", [])), _json(record.get("warnings", [])), now_iso(),
            ),
        )


def get_dataset_import(import_id: str) -> dict[str, Any] | None:
    with database() as connection:
        row = connection.execute("SELECT * FROM dataset_imports WHERE id = ?", (import_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["errors"] = _loads(result.pop("errors_json", None), [])
    result["warnings"] = _loads(result.pop("warnings_json", None), [])
    return result


def commit_dataset_import(import_id: str) -> None:
    with database() as connection:
        connection.execute(
            "UPDATE dataset_imports SET status = 'committed', committed_at = ? WHERE id = ?",
            (now_iso(), import_id),
        )


def replace_cases_from_import(import_id: str, rows: list[dict[str, Any]]) -> None:
    columns = (
        "id", "category", "district", "street", "description", "level", "priority", "status",
        "responsible_unit", "evidence_complete", "created_at", "resolved_at", "source",
    )
    placeholders = ",".join("?" for _ in columns)
    with database() as connection:
        connection.execute("DELETE FROM case_actions")
        connection.execute("DELETE FROM cases")
        connection.executemany(
            f"INSERT INTO cases ({','.join(columns)}) VALUES ({placeholders})",
            ([row[column] for column in columns] for row in rows),
        )
        connection.execute(
            "UPDATE dataset_imports SET status = 'committed', committed_at = ? WHERE id = ?",
            (now_iso(), import_id),
        )


def data_summary() -> dict[str, Any]:
    with database() as connection:
        metrics = connection.execute(
            "SELECT COUNT(*) AS count, MAX(created_at) AS latest_case_at FROM cases"
        ).fetchone()
        latest = connection.execute(
            """SELECT id, file_name, row_count, committed_at
               FROM dataset_imports WHERE status = 'committed'
               ORDER BY committed_at DESC LIMIT 1"""
        ).fetchone()
    return {
        "record_count": metrics["count"],
        "latest_case_at": metrics["latest_case_at"],
        "latest_import": dict(latest) if latest else None,
    }


def paged_case_rows(page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    offset = (page - 1) * page_size
    with database() as connection:
        total = connection.execute("SELECT COUNT(*) AS count FROM cases").fetchone()["count"]
        rows = [dict(row) for row in connection.execute(
            "SELECT * FROM cases ORDER BY created_at DESC LIMIT ? OFFSET ?", (page_size, offset)
        ).fetchall()]
    for row in rows:
        row["evidence_complete"] = bool(row["evidence_complete"])
    return rows, total


def create_agent_run(run_id: str, question: str) -> str:
    started_at = now_iso()
    with database() as connection:
        connection.execute(
            "INSERT INTO agent_runs (id, question, status, started_at) VALUES (?, ?, 'running', ?)",
            (run_id, question, started_at),
        )
        connection.execute(
            """DELETE FROM agent_runs WHERE id IN (
                   SELECT id FROM agent_runs ORDER BY started_at DESC LIMIT -1 OFFSET 500
               )"""
        )
    return started_at


def update_agent_run_intent(run_id: str, intent: str | None) -> None:
    with database() as connection:
        connection.execute("UPDATE agent_runs SET intent = ? WHERE id = ?", (intent, run_id))


def append_agent_run_step(run_id: str, item: dict[str, Any], position: int) -> None:
    with database() as connection:
        connection.execute(
            """INSERT INTO agent_run_steps
               (run_id, step_key, title, detail, status, occurred_at, position)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, str(item.get("step") or item.get("id") or f"step-{position}"),
                str(item.get("title") or "执行步骤"),
                str(item.get("summary") or item.get("detail") or ""),
                str(item.get("status") or "completed"), now_iso(), position,
            ),
        )


def finish_agent_run(
    run_id: str, *, status: str, answer: str = "", error_code: str | None = None,
    duration_ms: int, tools: list[str] | None = None, sources: list[dict[str, Any]] | None = None,
) -> None:
    with database() as connection:
        connection.execute(
            """UPDATE agent_runs SET status = ?, answer = ?, error_code = ?, finished_at = ?,
               duration_ms = ?, tools_json = ?, sources_json = ? WHERE id = ?""",
            (status, answer, error_code, now_iso(), duration_ms, _json(tools or []), _json(sources or []), run_id),
        )


def list_agent_runs(*, page: int, page_size: int, status: str | None, query: str | None) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if query:
        clauses.append("question LIKE ?")
        params.append(f"%{query}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with database() as connection:
        total = connection.execute(f"SELECT COUNT(*) AS count FROM agent_runs {where}", params).fetchone()["count"]
        rows = connection.execute(
            f"""SELECT id, question, intent, status, started_at, finished_at, duration_ms, tools_json, error_code
                FROM agent_runs {where} ORDER BY started_at DESC LIMIT ? OFFSET ?""",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["tools"] = _loads(item.pop("tools_json"), [])
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_agent_run(run_id: str) -> dict[str, Any] | None:
    with database() as connection:
        row = connection.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        steps = [dict(step) for step in connection.execute(
            """SELECT step_key, title, detail, status, occurred_at, position
               FROM agent_run_steps WHERE run_id = ? ORDER BY position""", (run_id,)
        ).fetchall()]
    result = dict(row)
    result["tools"] = _loads(result.pop("tools_json"), [])
    result["sources"] = _loads(result.pop("sources_json"), [])
    result["steps"] = steps
    return result
