#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
记忆模块：

- 短期记忆：放在 state.short_memory（结构化事实+简短摘要），通过 Prompt 注入到 Planner/Executor/Reporter。
- 长期记忆：双存储
  1) 事件日志（JSONL，便于审计/回放）
  2) 检索切片（从日志派生为 chunks，用 mock embedding 做相似度检索；真实环境可换向量库）
"""

from __future__ import annotations

import json
import math
import os
import time
from typing import Any, Optional

from ..retrieval.mock_data import _mock_embedding


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na * nb == 0:
        return 0.0
    return dot / (na * nb)


def _repo_root() -> str:
    # src/unicom_agent/memory/manager.py -> repo root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _memory_dir() -> str:
    d = os.path.join(_repo_root(), "data", "unicom_memory")
    os.makedirs(d, exist_ok=True)
    return d


def _memory_path(*, tenant_id: str, user_id: str) -> str:
    safe_tenant = (tenant_id or "default").replace("/", "_")
    safe_user = (user_id or "anonymous").replace("/", "_")
    return os.path.join(_memory_dir(), f"{safe_tenant}__{safe_user}.jsonl")


def _redact_phone(s: str) -> str:
    # 简单脱敏：11位手机号中间 4 位打码
    if not s:
        return s
    if len(s) == 11 and s.isdigit():
        return s[:3] + "****" + s[-4:]
    return s


def build_short_memory(state: dict[str, Any]) -> dict[str, Any]:
    """
    从 state 里提炼“当前对话短期记忆”：
    - 只保存对业务决策必要的事实（phone/amount/intent/最近错误提示等）
    - phone 默认脱敏保存（避免 prompt 泄露）
    """
    intent = state.get("intent") or "general"
    entities = dict(state.get("confirmed_entities") or {})
    auth = state.get("auth_context") or {}

    phone = entities.get("phone") or auth.get("phone")
    amount = entities.get("amount")

    last_err = None
    err = state.get("execution_error")
    if isinstance(err, dict) and err.get("hint"):
        last_err = str(err.get("hint"))

    facts: dict[str, Any] = {
        "intent": intent,
        "phone_masked": _redact_phone(str(phone)) if phone else None,
        "amount": amount,
        "has_pay_permission": ("PAY_BILL" in (auth.get("permissions") or [])) or ("ADMIN" in (auth.get("permissions") or [])),
        "last_error_hint": last_err,
    }

    summary_parts = [f"意图={intent}"]
    if facts.get("phone_masked"):
        summary_parts.append(f"号码={facts['phone_masked']}")
    if amount is not None:
        summary_parts.append(f"金额={amount}")
    if last_err:
        summary_parts.append(f"上次错误={last_err}")

    return {"facts": facts, "summary": "；".join(summary_parts)}


def format_memory_for_prompt(short_memory: Optional[dict[str, Any]], long_hits: Optional[list[dict[str, Any]]] = None) -> str:
    """
    给 Prompt 注入的记忆块（可控、简短）：
    - 短期记忆：对话内事实与摘要
    - 长期记忆：检索到的历史片段（已脱敏）
    """
    parts: list[str] = []
    if short_memory and (short_memory.get("summary") or short_memory.get("facts")):
        parts.append("【短期记忆（本次对话已确认信息）】")
        if short_memory.get("summary"):
            parts.append(str(short_memory["summary"]).strip())
        facts = short_memory.get("facts") or {}
        # 仅输出少量关键字段，避免 prompt 过长
        for k in ("intent", "phone_masked", "amount", "last_error_hint"):
            if facts.get(k) is not None and str(facts.get(k)).strip() != "":
                parts.append(f"- {k}: {facts.get(k)}")

    if long_hits:
        parts.append("【长期记忆（历史对话/事件检索）】")
        for h in long_hits[:5]:
            txt = (h.get("text") or "").strip()
            if txt:
                parts.append(f"- {txt}")

    return "\n".join(parts).strip()


def append_long_memory_event(
    *,
    tenant_id: str,
    user_id: str,
    event: dict[str, Any],
) -> None:
    """
    写入长期记忆事件日志（JSONL）。
    建议只写“可审计、可脱敏”的事件：用户意图、关键槽位（脱敏）、结果摘要等。
    """
    path = _memory_path(tenant_id=tenant_id, user_id=user_id)
    record = {
        "ts": int(time.time()),
        **(event or {}),
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_long_memory_events(*, tenant_id: str, user_id: str, limit: int = 2000) -> list[dict[str, Any]]:
    path = _memory_path(tenant_id=tenant_id, user_id=user_id)
    if not os.path.exists(path):
        return []
    events: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events[-limit:]


def search_long_memory(
    *,
    tenant_id: str,
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    从长期记忆事件日志派生 chunks 并用 mock embedding 做相似度检索。
    返回格式对齐召回：{"source","id","text","score","meta"}
    """
    events = _load_long_memory_events(tenant_id=tenant_id, user_id=user_id)
    if not events:
        return []

    # 事件 -> chunk 文本（尽量短）
    chunks: list[dict[str, Any]] = []
    for i, e in enumerate(events):
        user_text = (e.get("user") or "").strip()
        bot_text = (e.get("assistant") or "").strip()
        intent = (e.get("intent") or "").strip()
        phone = (e.get("phone") or "").strip()
        amount = e.get("amount")

        phone_masked = _redact_phone(phone) if phone else ""
        text_parts = []
        if intent:
            text_parts.append(f"意图={intent}")
        if phone_masked:
            text_parts.append(f"号码={phone_masked}")
        if amount is not None:
            text_parts.append(f"金额={amount}")
        if user_text:
            text_parts.append(f"用户说：{user_text}")
        if bot_text:
            text_parts.append(f"客服答：{bot_text}")
        text = "；".join(text_parts)
        if not text:
            continue
        chunks.append(
            {
                "id": f"mem_{i}",
                "text": text,
                "embedding": _mock_embedding(text),
                "meta": {"ts": e.get("ts")},
            }
        )

    q_emb = _mock_embedding(query or "")
    scored = []
    for c in chunks:
        score = _cosine_sim(q_emb, c["embedding"])
        scored.append(
            {
                "source": "memory",
                "id": c["id"],
                "text": c["text"],
                "score": round(float(score), 4),
                "meta": c.get("meta") or {},
            }
        )
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]

