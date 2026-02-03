# -*- coding: utf-8 -*-
"""
联通智能客服 - 模拟向量检索

基于 mock embedding 的余弦相似度检索，实际可替换为 Milvus / Qdrant / ES 等。
"""

from __future__ import annotations

import math
from typing import Any

from .mock_data import _mock_embedding, get_vector_chunks


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na * nb == 0:
        return 0.0
    return dot / (na * nb)


def search(
    query: str,
    top_k: int = 5,
    chunks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    向量检索：用 query 的 mock embedding 与库中向量做余弦相似度，返回 top_k。
    返回项格式：{"source": "vector", "id", "text", "score", "meta"}。
    """
    chunks = chunks or get_vector_chunks()
    q_emb = _mock_embedding(query)
    scored = []
    for c in chunks:
        emb = c.get("embedding") or _mock_embedding(c["text"])
        score = _cosine_sim(q_emb, emb)
        scored.append({
            "source": "vector",
            "id": c.get("id", ""),
            "text": c.get("text", ""),
            "score": round(score, 4),
            "meta": {"title": c.get("source", "")},
        })
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]
