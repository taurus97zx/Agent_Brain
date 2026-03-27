# -*- coding: utf-8 -*-
"""
联通智能客服 - 多路召回节点

在 Router 之后、Planner 之前执行：对 user_input + intent 做向量 + KG + 规则三路召回，
合并去重排序后写入 state.recall_results 与 state.retrieved_context，供后续 Planner/Reporter 使用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import UnicomAgentState


def retrieve(state: "UnicomAgentState") -> "UnicomAgentState":
    """
    多路召回节点：向量库 + 知识图谱 + 规则文档，合并去重排序。
    将结果写入 recall_results 与 retrieved_context。
    """
    from .retrieval import format_recall_for_context, multi_path_recall

    user_input = state.get("user_input") or ""
    intent = state.get("intent")
    query = user_input.strip() or "联通客服"
    top_k = 10

    # 长期记忆检索（双存储：事件日志 -> chunks -> 相似度）
    auth = state.get("auth_context") or {}
    tenant_id = auth.get("tenant_id") or "UNICOM_PUBLIC"
    user_id = auth.get("user_id") or "anonymous"
    long_hits = []
    try:
        from .memory import search_long_memory

        long_hits = search_long_memory(
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            query=query,
            top_k=5,
        )
    except Exception:
        long_hits = []

    recall_results = multi_path_recall(
        query=query,
        intent=intent,
        top_k=top_k,
        vector_top_k=5,
        kg_top_k=5,
        rule_top_k=5,
        use_rrf=True,
    )
    retrieved_context = format_recall_for_context(recall_results, max_chars=2000)

    # 记忆上下文：短期记忆 + 长期记忆命中（不混入检索上下文，避免污染召回）
    memory_context = ""
    try:
        from .memory import build_short_memory, format_memory_for_prompt

        short_mem = build_short_memory(state)
        memory_context = format_memory_for_prompt(short_mem, long_hits)
        state = {**state, "short_memory": short_mem}
    except Exception:
        memory_context = ""
    return {
        **state,
        "recall_results": recall_results,
        "retrieved_context": retrieved_context,
        "long_memory_hits": long_hits,
        "memory_context": memory_context or None,
    }
