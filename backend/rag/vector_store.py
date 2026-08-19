"""Small local lexical store. It keeps competition mode dependency-free and traceable."""
from __future__ import annotations

import json
import math
import os
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
        self.mode = "lexical"

    def build(self, documents: list[dict[str, Any]], embeddings: list[list[float]] | None = None) -> str:
        if embeddings is not None and len(embeddings) != len(documents):
            raise ValueError("向量数量与知识分块数量不一致")
        self.mode = "hybrid" if embeddings else "lexical"
        self.documents = [
            {**document, **({"embedding": embeddings[index]} if embeddings else {})}
            for index, document in enumerate(documents)
        ]
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.index_path.with_suffix(self.index_path.suffix + ".tmp")
        temporary_path.write_text(json.dumps({
            "version": 2, "mode": self.mode, "documents": self.documents,
        }, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary_path, self.index_path)
        return self.mode

    def load(self) -> bool:
        if not self.index_path.exists():
            return False
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            self.documents = payload
            self.mode = "lexical"
        else:
            self.documents = payload.get("documents", [])
            self.mode = payload.get("mode", "lexical")
        return True

    def search(
        self, query: str, limit: int = 4, min_score: float | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.documents and not self.load():
            return []
        if min_score is None:
            min_score = get_settings().rag_min_score
        query_terms = Counter(_terms(query))
        scored = []
        for document in self.documents:
            lexical_score = _cosine(query_terms, Counter(_terms(document["chunk"])))
            vector = document.get("embedding")
            if query_embedding is not None and vector and len(query_embedding) == len(vector):
                semantic_score = _vector_cosine(query_embedding, vector)
                score = semantic_score * 0.7 + lexical_score * 0.3
                retrieval_mode = "hybrid"
            else:
                score = lexical_score
                retrieval_mode = "lexical"
            if score >= min_score:
                result = {key: value for key, value in document.items() if key != "embedding"}
                scored.append({**result, "score": round(score, 4), "retrieval_mode": retrieval_mode})
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]


def _vector_cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return numerator / denominator if denominator else 0.0
