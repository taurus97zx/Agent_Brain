# -*- coding: utf-8 -*-
"""
联通智能客服 - 多路召回检索

模拟向量库 + 知识图谱 + 规则文档，三路召回合并排序，提升召回率。
"""

from .mock_data import (
    get_kg_entities,
    get_kg_relations,
    get_rule_docs,
    get_vector_chunks,
)
from .recall import format_recall_for_context, multi_path_recall
from .vector_store import search as vector_search
from .kg_store import search as kg_search
from .rule_store import search as rule_search

__all__ = [
    "multi_path_recall",
    "format_recall_for_context",
    "vector_search",
    "kg_search",
    "rule_search",
    "get_vector_chunks",
    "get_kg_entities",
    "get_kg_relations",
    "get_rule_docs",
]
