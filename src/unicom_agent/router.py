# -*- coding: utf-8 -*-
"""
联通智能客服 - Router 路由 Agent

支持大模型意图分类；无 API 或调用失败时回退到规则分类。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import IntentType, UnicomAgentState

# 意图枚举值（与 LLM 输出对齐）
INTENT_VALUES = ("pay_bill", "query_bill", "query_balance", "query_package", "general")

# 规则回退：意图关键词
INTENT_KEYWORDS = {
    "pay_bill": ["缴费", "交费", "充值", "付款", "还款", "缴话费", "交话费", "充话费"],
    "query_bill": ["账单", "欠费", "话费清单", "消费明细", "本月消费"],
    "query_balance": ["余额", "剩余", "还有多少", "查余额", "账户余额"],
    "query_package": ["套餐", "流量", "月租", "资费", "升级套餐", "改套餐"],
}


def _classify_intent_by_rules(user_input: str) -> "IntentType":
    """规则意图分类（无 LLM 时的回退）。"""
    text = (user_input or "").strip().lower()
    if not text:
        return "general"
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return intent  # type: ignore
    if re.search(r"(\d+)\s*元|(\d+)\s*块|交\s*\d+|充\s*\d+", text) and any(k in text for k in ["交", "充", "缴", "付"]):
        return "pay_bill"  # type: ignore
    return "general"


def _classify_intent_by_llm(user_input: str, config=None) -> "IntentType":
    """使用大模型做意图分类；输出经 Pydantic 校验，错误 schema 时回退规则。"""
    from .llm import UnicomLLMConfig, chat, parse_and_validate
    from .schemas import IntentOutput
    cfg = config or UnicomLLMConfig()
    if not cfg.api_key and "api.openai.com" in cfg.base_url:
        return _classify_intent_by_rules(user_input)
    sys_prompt = """你是联通智能客服的意图分类器。根据用户输入，只输出一个 JSON 对象，格式：{"intent": "标签"}。
标签只能是以下之一：pay_bill, query_bill, query_balance, query_package, general。
pay_bill=缴费/交费/充值，query_bill=查账单/欠费，query_balance=查余额，query_package=查套餐，general=其他。"""
    try:
        content = chat(
            [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_input or ""}],
            config=cfg,
            model=cfg.model_router,
        )
        validated = parse_and_validate(content or "", IntentOutput)
        if validated is not None:
            return validated.intent  # type: ignore
        # 兼容旧版：模型只输出纯标签
        raw = (content or "").strip().lower()
        for intent in INTENT_VALUES:
            if intent in raw or raw == intent:
                return intent  # type: ignore
    except Exception:
        pass
    return _classify_intent_by_rules(user_input)


def classify_intent(user_input: str, use_llm: bool = True, config=None) -> "IntentType":
    """
    意图分类。use_llm=True 时优先用大模型，失败或未配置则用规则。
    """
    if use_llm:
        return _classify_intent_by_llm(user_input, config)
    return _classify_intent_by_rules(user_input)


def route(state: "UnicomAgentState") -> "UnicomAgentState":
    """Router 节点：写入 intent、user_input。"""
    user_input = state.get("user_input") or ""
    if state.get("messages"):
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "content"):
            user_input = user_input or str(last_msg.content)
    config = state.get("llm_config")
    intent = classify_intent(user_input, use_llm=True, config=config)
    return {**state, "intent": intent, "user_input": user_input}
