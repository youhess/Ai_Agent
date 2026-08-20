import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_PATH"] = "backend/data/test.db"
os.environ["KNOWLEDGE_DIRECTORY"] = "knowledge"
# Unit tests must never call the developer's configured external model.
os.environ["LLM_API_KEY"] = ""
# Unit tests must never call a developer's configured external RAG workflow.
os.environ["RAG_PROVIDER"] = "local"
os.environ["XINGCHEN_RAG_API_URL"] = ""
os.environ["XINGCHEN_RAG_API_KEY"] = ""


@pytest.fixture(scope="session", autouse=True)
def demo_environment():
    from database.init_db import init_database
    from database.repository import replace_cases
    from rag.ingest import ingest_knowledge
    from scripts.generate_sample_data import generate

    init_database()
    replace_cases(generate())
    ingest_knowledge()
