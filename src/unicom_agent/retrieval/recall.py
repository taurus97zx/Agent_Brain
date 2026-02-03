# -*- coding: utf-8 -*-
"""
联通智能客服 - 多路召回

向量库 + 知识图谱 + 规则文档 三路召回，合并去重排序，提升召回率。
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from .kg_store import search as kg_search
from .rule_store import search as rule_search
from .vector_store import search as vector_search


# 各路权重（可调）：向量 / KG / 规则
SOURCE_WEIGHTS: dict[str, float] = {
    "vector": 1.0,
    "kg": 0.9,
    "rule": 1.0,
}


def _dedupe_by_id(items: list[dict], key_field: str = "id") -> list[dict]:
    """按 id 去重，保留首次出现（即得分最高的一次）。"""
    seen: set[str] = set()
    out = []
    for x in items:
        kid = x.get(key_field) or ""
        if kid and kid in seen:
            continue
        if kid:
            seen.add(kid)
        out.append(x)
    return out


def _content_hash(text: str) -> str:
    return hashlib.md5((text or "").strip().encode("utf-8")).hexdigest()[:16]


def _merge_and_rank(
    vector_results: list[dict],
    kg_results: list[dict],
    rule_results: list[dict],
    top_k: int = 10,
    use_rrf: bool = True,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """
    合并三路结果：按 (source, id) 去重，再按加权分或 RRF 排序取 top_k。
    RRF: 1/(k + rank)，k=60 时与常见实现一致。
    """
    # 统一格式：source, id, text, score, meta
    all_items: list[dict] = []
    for r in vector_results:
        r["_source"] = "vector"
        all_items.append(r)
    for r in kg_results:
        r["_source"] = "kg"
        all_items.append(r)
    for r in rule_results:
        r["_source"] = "rule"
        all_items.append(r)

    # 按 (source, id) 去重，保留得分最高
    by_key: dict[tuple[str, str], dict] = {}
    for x in all_items:
        key = (x.get("source", x.get("_source", "")), x.get("id", _content_hash(x.get("text", ""))))
        if key not in by_key or (x.get("score", 0) > by_key[key].get("score", 0)):
            by_key[key] = {k: v for k, v in x.items() if k != "_source"}
            by_key[key]["source"] = x.get("source", x.get("_source"))

    merged = list(by_key.values())

    if use_rrf:
        # 各路内部排名，再 RRF 加权
        def rank_score(item: dict, rank: int) -> float:
            w = SOURCE_WEIGHTS.get(item.get("source", ""), 1.0)
            return w / (rrf_k + rank)
        # 按 source 分组排序得到 rank
        by_src: dict[str, list[dict]] = {}
        for m in merged:
            s = m.get("source", "")
            by_src.setdefault(s, []).append(m)
        for s, lst in by_src.items():
            lst.sort(key=lambda x: -x.get("score", 0))
            for i, x in enumerate(lst):
                x["_rrf_rank"] = i + 1
                x["_rrf_score"] = rank_score(x, i + 1)
        merged.sort(key=lambda x: -x.get("_rrf_score", 0))
    else:
        # 简单加权：score * source_weight
        for m in merged:
            m["_rrf_score"] = (m.get("score", 0) or 0) * SOURCE_WEIGHTS.get(m.get("source", ""), 1.0)
        merged.sort(key=lambda x: -x.get("_rrf_score", 0))

    # 去掉内部字段，只保留对外字段
    out = []
    for m in merged[:top_k]:
        out.append({
            "source": m.get("source"),
            "id": m.get("id"),
            "text": m.get("text"),
            "score": m.get("score"),
            "meta": m.get("meta"),
        })
    return out


def multi_path_recall(
    query: str,
    intent: str | None = None,
    top_k: int = 10,
    vector_top_k: int = 5,
    kg_top_k: int = 5,
    rule_top_k: int = 5,
    use_rrf: bool = True,
) -> list[dict[str, Any]]:
    """
    多路召回：向量 + 知识图谱 + 规则文档，合并去重排序。

    - query: 用户问句或检索 query
    - intent: 可选，用于规则文档的 scope 过滤（如 pay_bill, query_bill）
    - top_k: 最终返回条数
    - vector_top_k / kg_top_k / rule_top_k: 各路召回条数
    - use_rrf: True 时用 RRF 排序，False 时用加权分

    返回格式：[{"source", "id", "text", "score", "meta"}, ...]
    """
    vector_results = vector_search(query, top_k=vector_top_k)
    kg_results = kg_search(query, top_k=kg_top_k)
    rule_results = rule_search(query, top_k=rule_top_k, scope=intent)

    return _merge_and_rank(
        vector_results,
        kg_results,
        rule_results,
        top_k=top_k,
        use_rrf=use_rrf,
    )


def format_recall_for_context(recall_results: list[dict], max_chars: int = 2000) -> str:
    """将召回结果格式化为可拼进 Prompt 的上下文字符串。"""
    parts = []
    total = 0
    for r in recall_results:
        t = (r.get("text") or "").strip()
        if not t:
            continue
        line = f"[{r.get('source', '')}] {t}"
        if total + len(line) + 1 > max_chars:
            break
        parts.append(line)
        total += len(line) + 1
    return "\n".join(parts) if parts else ""
