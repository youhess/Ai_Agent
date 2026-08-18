from datetime import datetime, timedelta
from typing import Any

from database.connection import database


ALLOWED_FILTERS = {"district", "category", "status", "priority"}


def query_cases(
    *, district: str | None = None, category: str | None = None,
    status: str | None = None, priority: str | None = None,
    days: int | None = None, start_date: str | None = None,
    end_date: str | None = None, limit: int = 200,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    filters = {"district": district, "category": category, "status": status, "priority": priority}
    for field, value in filters.items():
        if value:
            clauses.append(f"{field} = ?")
            params.append(value)
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
        return dict(row) if row else None


def replace_cases(rows: list[dict[str, Any]]) -> None:
    columns = ("id", "category", "district", "street", "description", "priority", "status", "created_at", "resolved_at", "source")
    placeholders = ",".join("?" for _ in columns)
    with database() as connection:
        connection.execute("DELETE FROM cases")
        connection.executemany(
            f"INSERT INTO cases ({','.join(columns)}) VALUES ({placeholders})",
            ([row[column] for column in columns] for row in rows),
        )
