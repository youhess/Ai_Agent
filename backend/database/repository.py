from datetime import datetime, timedelta
from typing import Any

from database.connection import database


ALLOWED_FILTERS = {"district", "street", "category", "status", "level", "priority"}


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
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def get_case(case_id: str) -> dict[str, Any] | None:
    with database() as connection:
        row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["evidence_complete"] = bool(result["evidence_complete"])
        result["timeline"] = [dict(item) for item in connection.execute(
            "SELECT action, operator_role, occurred_at, note FROM case_actions WHERE case_id = ? ORDER BY occurred_at",
            (case_id,),
        ).fetchall()]
        return result


def replace_cases(rows: list[dict[str, Any]]) -> None:
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
        actions = []
        for row in rows:
            for item in row.get("timeline", []):
                actions.append((row["id"], item["action"], item["operator_role"], item["occurred_at"], item["note"]))
        connection.executemany(
            "INSERT INTO case_actions (case_id, action, operator_role, occurred_at, note) VALUES (?, ?, ?, ?, ?)",
            actions,
        )
