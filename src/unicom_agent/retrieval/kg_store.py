# -*- coding: utf-8 -*-
"""
联通智能客服 - 模拟知识图谱检索

根据 query 关键词匹配实体，并召回相邻实体与关系三元组，实际可替换为 Neo4j / Nebula 等。
"""

from __future__ import annotations

from typing import Any

from .mock_data import get_kg_entities, get_kg_relations


def _keyword_match_score(query: str, keywords: list[str]) -> float:
    q = (query or "").strip().lower()
    if not q or not keywords:
        return 0.0
    hits = sum(1 for k in keywords if k in q or q in k)
    return hits / max(len(keywords), 1)


def search(
    query: str,
    top_k: int = 5,
    expand_hop: int = 1,
    entities: list[dict] | None = None,
    relations: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """
    知识图谱检索：用 query 匹配实体关键词，召回实体及 expand_hop 跳内的邻居与三元组。
    返回项格式：{"source": "kg", "id", "text", "score", "meta": {entities, relations}}。
    """
    entities = entities or get_kg_entities()
    relations = relations or get_kg_relations()

    # 1. 匹配实体
    matched = []
    for e in entities:
        kw = e.get("keywords") or []
        score = _keyword_match_score(query, kw)
        if score > 0:
            matched.append({"entity": e, "score": score})

    matched.sort(key=lambda x: -x["score"])
    matched = matched[: top_k * 2]

    # 2. 扩展邻居（一跳）
    entity_ids = {m["entity"]["id"] for m in matched}
    if expand_hop >= 1:
        for r in relations:
            h, t = r.get("head"), r.get("tail")
            if h in entity_ids or t in entity_ids:
                entity_ids.add(h)
                entity_ids.add(t)

    # 3. 构建召回文本
    id_to_entity = {e["id"]: e for e in entities}
    rel_texts = []
    for r in relations:
        if r.get("head") in entity_ids or r.get("tail") in entity_ids:
            h_name = id_to_entity.get(r["head"], {}).get("name", r["head"])
            t_name = id_to_entity.get(r["tail"], {}).get("name", r["tail"])
            rel_texts.append(f"{h_name}-{r.get('relation', '')}-{t_name}")

    # 4. 返回格式与 vector_store 一致
    result = []
    seen = set()
    for m in matched[:top_k]:
        e = m["entity"]
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        text = e.get("name", "") + "：" + ",".join(e.get("keywords", []))
        result.append({
            "source": "kg",
            "id": e["id"],
            "text": text,
            "score": round(m["score"], 4),
            "meta": {"entities": list(entity_ids), "relations": rel_texts[:10]},
        })
    if not result and rel_texts:
        result.append({
            "source": "kg",
            "id": "kg_relations",
            "text": "；".join(rel_texts[:5]),
            "score": 0.5,
            "meta": {"relations": rel_texts},
        })
    return result[:top_k]
