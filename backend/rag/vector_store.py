"""Small local lexical store. It keeps competition mode dependency-free and traceable."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from config import get_settings


def _terms(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    chinese = [normalized[index:index + 2] for index in range(max(0, len(normalized) - 1))]
    latin = re.findall(r"[a-z0-9_]{2,}", text.lower())
    return chinese + latin


def _cosine(left: Counter, right: Counter) -> float:
    numerator = sum(value * right.get(term, 0) for term, value in left.items())
    denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(sum(value * value for value in right.values()))
    return numerator / denominator if denominator else 0.0


class LocalVectorStore:
    def __init__(self, index_path: Path | None = None):
        self.index_path = index_path or get_settings().database_file.parent / "rag_index.json"
        self.documents: list[dict[str, Any]] = []

    def build(self, documents: list[dict[str, str]]) -> None:
        self.documents = documents
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> bool:
        if not self.index_path.exists():
            return False
        self.documents = json.loads(self.index_path.read_text(encoding="utf-8"))
        return True

    def search(self, query: str, limit: int = 4) -> list[dict[str, Any]]:
        if not self.documents and not self.load():
            return []
        query_terms = Counter(_terms(query))
        scored = []
        for document in self.documents:
            score = _cosine(query_terms, Counter(_terms(document["chunk"])))
            if score > 0:
                scored.append({**document, "score": round(score, 4)})
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]
