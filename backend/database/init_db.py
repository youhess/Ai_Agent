from database.connection import database


SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    district TEXT NOT NULL,
    street TEXT NOT NULL,
    description TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('一级', '二级', '三级')),
    priority TEXT NOT NULL CHECK (priority IN ('低', '中', '高')),
    status TEXT NOT NULL CHECK (status IN ('待处理', '处理中', '已完成')),
    responsible_unit TEXT NOT NULL,
    evidence_complete INTEGER NOT NULL DEFAULT 0 CHECK (evidence_complete IN (0, 1)),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    operator_role TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    note TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at);
CREATE INDEX IF NOT EXISTS idx_cases_district ON cases(district);
CREATE INDEX IF NOT EXISTS idx_cases_category ON cases(category);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_case_actions_case_id ON case_actions(case_id);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    stored_name TEXT,
    source_type TEXT NOT NULL CHECK (source_type IN ('built_in', 'uploaded')),
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    index_mode TEXT NOT NULL DEFAULT 'lexical',
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    indexed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_documents_sha256 ON knowledge_documents(sha256);
CREATE INDEX IF NOT EXISTS idx_knowledge_documents_status ON knowledge_documents(status);

CREATE TABLE IF NOT EXISTS dataset_imports (
    id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    committed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_dataset_imports_created_at ON dataset_imports(created_at);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    intent TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    answer TEXT NOT NULL DEFAULT '',
    error_code TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    tools_json TEXT NOT NULL DEFAULT '[]',
    sources_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at ON agent_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);

CREATE TABLE IF NOT EXISTS agent_run_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    step_key TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT,
    status TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    position INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_run_steps_run_id ON agent_run_steps(run_id, position);
"""


def init_database() -> None:
    with database() as connection:
        connection.executescript(SCHEMA)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(cases)").fetchall()}
        if "level" not in columns:
            connection.execute("ALTER TABLE cases ADD COLUMN level TEXT NOT NULL DEFAULT '三级'")
        if "responsible_unit" not in columns:
            connection.execute("ALTER TABLE cases ADD COLUMN responsible_unit TEXT NOT NULL DEFAULT '待分派单位'")
        if "evidence_complete" not in columns:
            connection.execute("ALTER TABLE cases ADD COLUMN evidence_complete INTEGER NOT NULL DEFAULT 0")


if __name__ == "__main__":
    init_database()
    print("Database initialized.")
