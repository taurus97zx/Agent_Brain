# -*- coding: utf-8 -*-
"""
联通智能客服 - Executor 执行 Agent

设计原则：
- 参数提取可用小模型（7B/14B）
- 权限校验不可欺骗：auth_context.has_permission(...)
- 执行失败通过 Error Adapter 转为业务态错误，不暴露技术细节给 Planner
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .tools.billing import (
    execute_payment,
    query_balance,
    query_bill,
    validate_user,
)

if TYPE_CHECKING:
    from .state import PlanStep, UnicomAgentState


# 缴费相关需显式权限
PAYMENT_PERMISSION = "PAY_BILL"


def _extract_phone(state: "UnicomAgentState") -> str | None:
    """从 state 或 auth 中取手机号。"""
    auth = state.get("auth_context") or {}
    if auth.get("phone"):
        return auth["phone"]
    entities = state.get("confirmed_entities") or {}
    return entities.get("phone")


def _extract_amount(user_input: str) -> float | None:
    """简单正则提取金额（可替换为小模型）。"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*元", user_input)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*块", user_input)
    if m:
        return float(m.group(1))
    m = re.search(r"交\s*(\d+)", user_input)
    if m:
        return float(m.group(1))
    return None


def _run_step(step: "PlanStep", state: "UnicomAgentState") -> dict[str, Any]:
    """执行单步，返回 step_results 条目。"""
    action = step.get("action")
    auth = state.get("auth_context") or {}
    phone = _extract_phone(state)
    user_input = state.get("user_input") or ""
    step_id = step.get("action", "unknown")

    if action == "validate_user":
        if not phone:
            return {"ok": False, "reason": "请先提供手机号或登录"}
        return validate_user(phone, auth)

    if action == "query_bill":
        if not phone:
            return {"ok": False, "reason": "需要手机号"}
        return query_bill(phone)

    if action == "query_balance":
        if not phone:
            return {"ok": False, "reason": "需要手机号"}
        return query_balance(phone)

    if action == "extract_params":
        amount = _extract_amount(user_input)
        entities = dict(state.get("confirmed_entities") or {})
        if phone:
            entities["phone"] = phone
        if amount is not None:
            entities["amount"] = amount
        return {"ok": True, "confirmed_entities": entities}

    if action == "execute_payment":
        # 不可欺骗的权限校验
        perms = auth.get("permissions") or []
        if PAYMENT_PERMISSION not in perms and "ADMIN" not in perms:
            return {
                "ok": False,
                "reason": "您没有缴费权限，请登录或联系客服",
                "error_type": "PERMISSION_DENIED",
            }
        entities = state.get("confirmed_entities") or {}
        amount = entities.get("amount")
        if amount is None:
            amount = _extract_amount(user_input)
        if amount is None or amount <= 0:
            return {"ok": False, "reason": "请提供有效缴费金额"}
        phone = phone or entities.get("phone")
        if not phone:
            return {"ok": False, "reason": "需要手机号"}
        return execute_payment(phone, float(amount), auth_context=auth)

    return {"ok": False, "reason": f"未知动作: {action}"}


def executor(state: "UnicomAgentState") -> "UnicomAgentState":
    """
    Executor 节点：执行 plan 中当前步骤。
    若 step 为 Reporter，不在此执行；只执行 Executor 的 action。
    """
    plan = state.get("plan")
    if not plan or not plan.get("steps"):
        return {**state, "execution_error": {"hint": "无有效规划", "action_required": "REGENERATE_PLAN"}}

    idx = state.get("current_step_index", 0)
    steps = plan["steps"]
    if idx >= len(steps):
        return {**state, "final_response": "处理完成", "should_end": True}

    step = steps[idx]
    if step.get("agent") != "Executor":
        # 下一步是 Reporter，本节点只推进索引由 workflow 处理
        return {**state, "current_step_index": idx + 1}

    result = _run_step(step, state)
    step_results = dict(state.get("step_results") or {})
    step_results[step.get("action", "step")] = result

    # 更新 confirmed_entities
    confirmed = dict(state.get("confirmed_entities") or {})
    if result.get("confirmed_entities"):
        confirmed.update(result["confirmed_entities"])

    # 业务失败 -> 写入 execution_error，不暴露技术细节
    if not result.get("ok"):
        return {
            **state,
            "step_results": step_results,
            "execution_error": {
                "event": "EXECUTION_FAILED",
                "failure_mode": "BUSINESS_RULE",
                "hint": result.get("reason", "执行失败"),
                "action_required": "RETRY_OR_ABORT",
            },
            "should_end": True,
        }

    next_idx = idx + 1
    return {
        **state,
        "step_results": step_results,
        "confirmed_entities": confirmed,
        "current_step_index": next_idx,
        "execution_error": None,
    }
