from generate_sample_data import generate

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from database.init_db import init_database  # noqa: E402
from database.repository import replace_cases  # noqa: E402
from rag.ingest import ingest_knowledge  # noqa: E402


if __name__ == "__main__":
    init_database()
    rows = generate()
    replace_cases(rows)
    chunks = ingest_knowledge()
    print(f"Demo ready: {len(rows)} cases, {chunks} knowledge chunks.")
