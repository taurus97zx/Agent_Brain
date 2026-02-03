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
    return {
        **state,
        "recall_results": recall_results,
        "retrieved_context": retrieved_context,
    }
