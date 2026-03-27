# -*- coding: utf-8 -*-
"""
敏感业务降级转接 Skill。

目标：
- 将“涉及金额/缴费权限/执行失败”的降级与转接规则集中管理
- Agent 只需调用 `evaluate_handoff`，统一得到是否转接与标准话术
"""

from __future__ import annotations

from typing import Any


def _contains_amount(user_input: str) -> bool:
    text = (user_input or "").strip()
    if not text:
        return False
    keywords = ["元", "块", "金额", "充值", "缴费", "交费", "付款", "支付"]
    if any(k in text for k in keywords):
        return True
    return False


def _is_sensitive_intent(intent: str) -> bool:
    return intent in {"pay_bill"}


def evaluate_handoff(state: dict[str, Any]) -> dict[str, Any]:
    """
    返回：
    {
      "need_handoff": bool,
      "reason_code": str,
      "message": str
    }
    """
    intent = str(state.get("intent") or "general")
    user_input = str(state.get("user_input") or "")
    err = state.get("execution_error") or {}
    step_results = state.get("step_results") or {}
    confirmed = state.get("confirmed_entities") or {}

    # 1) 明确权限问题：直接转接人工
    if isinstance(err, dict):
        hint = str(err.get("hint") or "")
        if "没有缴费权限" in hint or "权限" in hint:
            return {
                "need_handoff": True,
                "reason_code": "PERMISSION_DENIED",
                "message": "当前请求涉及敏感缴费权限，已为您转接人工客服进一步核验处理。",
            }

    # 2) 涉及金额的缴费请求，且参数不完整：先转接人工，避免误操作
    if _is_sensitive_intent(intent) and _contains_amount(user_input):
        amount = confirmed.get("amount")
        if amount is None:
            return {
                "need_handoff": True,
                "reason_code": "PAYMENT_PARAM_INCOMPLETE",
                "message": "该请求涉及金额处理且信息不完整，为保障资金安全，已为您转接人工客服协助办理。",
            }

    # 3) 执行缴费失败：统一走人工兜底
    pay_result = step_results.get("execute_payment") or {}
    if isinstance(pay_result, dict) and pay_result.get("ok") is False:
        return {
            "need_handoff": True,
            "reason_code": "PAYMENT_EXECUTE_FAILED",
            "message": "缴费请求处理失败。为避免重复扣款风险，已为您转接人工客服继续处理。",
        }

    return {"need_handoff": False, "reason_code": "", "message": ""}

