import json
from datetime import datetime, timedelta
from typing import Any

from database.connection import database


ALLOWED_FILTERS = {"district", "street", "category", "status", "level", "priority"}


class WorkflowConflict(ValueError):
    """The requested workflow transition is not valid for the case's current state."""


def _case_dict(row: Any) -> dict[str, Any]:
    result = dict(row)
    result["evidence_complete"] = bool(result.get("evidence_complete"))
    raw_collaborators = result.get("collaborator_units") or "[]"
    try:
        collaborators = json.loads(raw_collaborators) if isinstance(raw_collaborators, str) else raw_collaborators
    except json.JSONDecodeError:
        collaborators = []
    result["collaborator_units"] = collaborators if isinstance(collaborators, list) else []
    result["updated_at"] = result.get("updated_at") or result.get("created_at")
    return result


def query_cases(
    *, district: str | None = None, street: str | None = None, category: str | None = None,
    status: str | None = None, statuses: list[str] | None = None, level: str | None = None,
    priority: str | None = None, evidence_complete: bool | None = None,
    days: int | None = None, start_date: str | None = None,
    end_date: str | None = None, keyword: str | None = None, limit: int = 200,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    filters = {"district": district, "street": street, "category": category, "status": status, "level": level, "priority": priority}
    for field, value in filters.items():
        if value:
            clauses.append(f"{field} = ?")
            params.append(value)
    if statuses:
        normalized_statuses = [value for value in statuses if value in {"待处理", "处理中", "已完成"}]
        if normalized_statuses:
            clauses.append(f"status IN ({','.join('?' for _ in normalized_statuses)})")
            params.extend(normalized_statuses)
    if evidence_complete is not None:
        clauses.append("evidence_complete = ?")
        params.append(int(evidence_complete))
    if keyword:
        clauses.append("(id LIKE ? OR description LIKE ? OR district LIKE ? OR street LIKE ? OR category LIKE ?)")
        pattern = f"%{keyword.strip()}%"
        params.extend([pattern] * 5)
    if days is not None:
        if not 1 <= days <= 3650:
            raise ValueError("days 必须在 1 到 3650 之间")
        clauses.append("created_at >= ?")
        params.append((datetime.now() - timedelta(days=days)).isoformat(timespec="seconds"))
    if start_date:
        clauses.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("created_at <= ?")
        params.append(end_date)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM cases {where} ORDER BY created_at DESC LIMIT ?"
    params.append(max(1, min(limit, 1000)))
    with database() as connection:
        return [_case_dict(row) for row in connection.execute(sql, params).fetchall()]


def get_case(case_id: str) -> dict[str, Any] | None:
    with database() as connection:
        row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            return None
        result = _case_dict(row)
        result["timeline"] = [dict(item) for item in connection.execute(
            "SELECT action, operator_role, occurred_at, note FROM case_actions WHERE case_id = ? ORDER BY occurred_at",
            (case_id,),
        ).fetchall()]
        return result


def advance_case_workflow(
    case_id: str,
    *,
    action: str,
    responsible_unit: str | None = None,
    collaborator_units: list[str] | None = None,
    evidence_complete: bool | None = None,
    note: str | None = None,
    operator_role: str = "基层治理协同智能体（人工确认）",
) -> dict[str, Any] | None:
    """Atomically advance a case and append a traceable business action."""
    now = datetime.now().replace(microsecond=0).isoformat(timespec="seconds")
    clean_note = (note or "").strip()
    with database() as connection:
        row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            return None
        current = _case_dict(row)
        status = current["status"]
        primary_unit = (responsible_unit or current.get("responsible_unit") or "").strip()
        collaborators = list(dict.fromkeys(
            value.strip() for value in (collaborator_units or current.get("collaborator_units") or [])
            if value and value.strip() and value.strip() != primary_unit
        ))

        if action == "dispatch":
            if status != "待处理":
                raise WorkflowConflict(f"事件当前为“{status}”，只有待处理事件可以派单")
            if not primary_unit or primary_unit == "待分派单位":
                raise WorkflowConflict("派单前必须明确主办单位")
            action_name = "智能协同派单"
            default_note = f"主办单位：{primary_unit}"
            if collaborators:
                default_note += f"；协办单位：{'、'.join(collaborators)}"
            connection.execute(
                """UPDATE cases
                   SET status = '处理中', responsible_unit = ?, collaborator_units = ?,
                       evidence_complete = 0, resolved_at = NULL, updated_at = ?
                   WHERE id = ?""",
                (primary_unit, json.dumps(collaborators, ensure_ascii=False), now, case_id),
            )
        elif action == "submit_result":
            if status != "处理中":
                raise WorkflowConflict(f"事件当前为“{status}”，只有处理中事件可以提交处置结果")
            if evidence_complete is None:
                raise WorkflowConflict("提交处置结果时必须明确证据是否完整")
            action_name = "提交处置结果"
            default_note = "已提交现场处置反馈；证据材料完整" if evidence_complete else "已提交阶段性反馈；证据仍需补充"
            connection.execute(
                "UPDATE cases SET evidence_complete = ?, updated_at = ? WHERE id = ?",
                (int(evidence_complete), now, case_id),
            )
        elif action == "return_for_rework":
            if status != "处理中":
                raise WorkflowConflict(f"事件当前为“{status}”，只有处理中事件可以退回补充")
            action_name = "复核退回补充"
            default_note = "复核未通过，已退回主办单位补充处置结果和证据"
            connection.execute(
                "UPDATE cases SET evidence_complete = 0, resolved_at = NULL, updated_at = ? WHERE id = ?",
                (now, case_id),
            )
        elif action == "approve_close":
            if status != "处理中":
                raise WorkflowConflict(f"事件当前为“{status}”，只有处理中事件可以复核办结")
            if not current["evidence_complete"]:
                raise WorkflowConflict("处置证据尚不完整，不能办结；请先提交完整结果或退回补充")
            action_name = "智能复核办结"
            default_note = "处置结果与证据复核通过，事件已办结归档"
            connection.execute(
                "UPDATE cases SET status = '已完成', resolved_at = ?, updated_at = ? WHERE id = ?",
                (now, now, case_id),
            )
        else:
            raise WorkflowConflict("不支持的治理流程动作")

        connection.execute(
            """INSERT INTO case_actions (case_id, action, operator_role, occurred_at, note)
               VALUES (?, ?, ?, ?, ?)""",
            (case_id, action_name, operator_role.strip() or "基层治理协同智能体（人工确认）", now, clean_note or default_note),
        )

    return get_case(case_id)


def replace_cases(rows: list[dict[str, Any]]) -> None:
    columns = (
        "id", "category", "district", "street", "description", "level", "priority", "status",
        "responsible_unit", "collaborator_units", "evidence_complete", "created_at", "updated_at", "resolved_at", "source",
    )
    placeholders = ",".join("?" for _ in columns)
    with database() as connection:
        connection.execute("DELETE FROM case_actions")
        connection.execute("DELETE FROM cases")
        connection.executemany(
            f"INSERT INTO cases ({','.join(columns)}) VALUES ({placeholders})",
            (
                [
                    json.dumps(row.get("collaborator_units", []), ensure_ascii=False) if column == "collaborator_units"
                    else row.get("updated_at", row["created_at"]) if column == "updated_at"
                    else row[column]
                    for column in columns
                ]
                for row in rows
            ),
        )
        actions = []
        for row in rows:
            for item in row.get("timeline", []):
                actions.append((row["id"], item["action"], item["operator_role"], item["occurred_at"], item["note"]))
        connection.executemany(
            "INSERT INTO case_actions (case_id, action, operator_role, occurred_at, note) VALUES (?, ?, ?, ?, ?)",
            actions,
        )
