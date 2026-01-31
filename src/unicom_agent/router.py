# -*- coding: utf-8 -*-
"""
联通智能客服 - Router 路由 Agent

设计原则（与 Graph-RAG-Agent 一致）：
- Router 是**确定性裁决器**，非 LLM
- 根据系统可信字段（或简单规则/小模型）映射唯一意图
- 租户身份来自登录态（auth_context），此处仅做意图分类
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import IntentType, UnicomAgentState


# 意图关键词映射（可替换为小模型或远程分类接口）
INTENT_KEYWORDS = {
    "pay_bill": ["缴费", "交费", "充值", "付款", "还款", "缴话费", "交话费", "充话费"],
    "query_bill": ["账单", "欠费", "话费清单", "消费明细", "本月消费"],
    "query_balance": ["余额", "剩余", "还有多少", "查余额", "账户余额"],
    "query_package": ["套餐", "流量", "月租", "资费", "升级套餐", "改套餐"],
}


def classify_intent(user_input: str) -> "IntentType":
    """
    基于规则的意图分类（可替换为 Qwen-7B 等小模型做简单分类）。
    不依赖用户自称身份，仅根据语义分类。
    """
    text = (user_input or "").strip().lower()
    if not text:
        return "general"

    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return intent  # type: ignore

    # 金额 + 缴费相关句式
    if re.search(r"(\d+)\s*元|(\d+)\s*块|交\s*\d+|充\s*\d+", text):
        if any(k in text for k in ["交", "充", "缴", "付"]):
            return "pay_bill"  # type: ignore

    return "general"


def route(state: "UnicomAgentState") -> "UnicomAgentState":
    """
    Router 节点：写入 intent，不修改 messages。
    下游根据 state["intent"] 做条件边。
    """
    user_input = state.get("user_input") or ""
    if state.get("messages"):
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "content"):
            user_input = user_input or str(last_msg.content)
    intent = classify_intent(user_input)
    return {**state, "intent": intent, "user_input": user_input}
