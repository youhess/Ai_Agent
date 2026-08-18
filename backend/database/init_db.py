from database.connection import database


SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    district TEXT NOT NULL,
    street TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('低', '中', '高')),
    status TEXT NOT NULL CHECK (status IN ('待处理', '处理中', '已完成')),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at);
CREATE INDEX IF NOT EXISTS idx_cases_district ON cases(district);
CREATE INDEX IF NOT EXISTS idx_cases_category ON cases(category);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
"""


def init_database() -> None:
    with database() as connection:
        connection.executescript(SCHEMA)


if __name__ == "__main__":
    init_database()
    print("Database initialized.")
