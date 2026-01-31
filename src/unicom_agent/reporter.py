# -*- coding: utf-8 -*-
"""
联通智能客服 - Reporter 应答 Agent

设计原则：
- 中模型或模板生成回复，可缓存 System Prompt
- 根据 step_results 和 intent 生成用户可见的最终回复
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import IntentType, UnicomAgentState


def _format_bill_response(step_results: dict) -> str:
    data = step_results.get("query_bill") or {}
    if not data.get("ok"):
        return data.get("reason", "查询失败，请稍后再试。")
    items = data.get("items", [])
    total = data.get("total", 0)
    lines = ["您的账单明细如下："]
    for it in items:
        lines.append(f"  - {it.get('item', '')}：{it.get('amount', 0)} 元")
    lines.append(f"合计：{total} 元")
    return "\n".join(lines)


def _format_balance_response(step_results: dict) -> str:
    data = step_results.get("query_balance") or {}
    if not data.get("ok"):
        return data.get("reason", "查询失败，请稍后再试。")
    balance = data.get("balance", 0)
    return f"您当前账户余额为：{balance} 元。"


def _format_payment_response(step_results: dict) -> str:
    data = step_results.get("execute_payment") or {}
    if not data.get("ok"):
        return data.get("reason", "缴费失败，请稍后再试。")
    return data.get("message", "缴费成功。")


def reporter(state: "UnicomAgentState") -> "UnicomAgentState":
    """
    Reporter 节点：根据 intent 与 step_results 生成最终回复。
    """
    intent = state.get("intent") or "general"
    step_results = state.get("step_results") or {}
    err = state.get("execution_error")

    if err:
        return {
            **state,
            "final_response": err.get("hint", "处理遇到问题，请稍后再试。"),
            "should_end": True,
        }

    if intent == "pay_bill":
        text = _format_payment_response(step_results)
    elif intent == "query_bill":
        text = _format_bill_response(step_results)
    elif intent == "query_balance":
        text = _format_balance_response(step_results)
    elif intent == "query_package":
        text = "您可登录中国联通 APP 或拨打 10010 查询与变更套餐。"
    else:
        text = "您好，我是联通智能客服。您可以问我：缴费、查账单、查余额、查套餐等。"

    return {
        **state,
        "final_response": text,
        "should_end": True,
    }
