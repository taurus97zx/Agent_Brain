# -*- coding: utf-8 -*-
"""
联通智能客服 - 模拟规则文档检索

基于关键词与 scope 匹配规则文档，实际可替换为 ES / 文档库等。
"""

from __future__ import annotations

from typing import Any

from .mock_data import get_rule_docs


def _keyword_score(query: str, keywords: list[str], content: str) -> float:
    q = (query or "").strip().lower()
    if not q:
        return 0.0
    score = 0.0
    for k in (keywords or []):
        if k in q or q in k:
            score += 0.3
    content_lower = (content or "").lower()
    for w in q.split():
        if len(w) >= 2 and w in content_lower:
            score += 0.2
    return min(score, 1.0)


def search(
    query: str,
    top_k: int = 5,
    scope: str | None = None,
    rule_docs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    规则文档检索：按关键词与 scope 匹配规则，返回 top_k。
    返回项格式：{"source": "rule", "id", "text", "score", "meta"}。
    """
    rule_docs = rule_docs or get_rule_docs()
    scored = []
    for r in rule_docs:
        if scope and r.get("scope") and scope != r.get("scope"):
            continue
        kw = r.get("keywords") or []
        content = (r.get("content") or "") + " " + (r.get("title") or "")
        score = _keyword_score(query, kw, content)
        if score > 0:
            scored.append({
                "source": "rule",
                "id": r.get("id", ""),
                "text": (r.get("title") or "") + "：" + (r.get("content") or ""),
                "score": round(score, 4),
                "meta": {"scope": r.get("scope"), "title": r.get("title")},
            })
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]
