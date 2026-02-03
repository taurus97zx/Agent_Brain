# -*- coding: utf-8 -*-
"""
联通智能客服 - Executor 执行 Agent

参数提取支持大模型；无 API 或失败时回退到正则提取。权限校验不可欺骗。
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

PAYMENT_PERMISSION = "PAY_BILL"


def _extract_phone(state: "UnicomAgentState") -> str | None:
    auth = state.get("auth_context") or {}
    if auth.get("phone"):
        return auth["phone"]
    entities = state.get("confirmed_entities") or {}
    return entities.get("phone")


def _extract_amount_by_rules(user_input: str) -> float | None:
    """规则回退：正则提取金额。"""
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


def _extract_params_by_llm(user_input: str, config=None) -> dict[str, Any]:
    """大模型提取：手机号、金额等。"""
    from .llm import UnicomLLMConfig, chat, parse_json_from_content
    cfg = config or UnicomLLMConfig()
    if not cfg.api_key and "api.openai.com" in cfg.base_url:
        return {}
    sys_prompt = """从用户输入中提取联通客服所需参数，只输出 JSON，不要其他文字。
字段：phone（11位手机号，若未提及填 null）、amount（缴费金额数字，未提及填 null）。
示例：{"phone": null, "amount": 50} 或 {"phone": "13800138000", "amount": 100}"""
    try:
        content = chat(
            [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_input or ""}],
            config=cfg,
            model=cfg.model_executor,
        )
        parsed = parse_json_from_content(content)
        if isinstance(parsed, dict):
            out = {}
            if parsed.get("phone") and re.match(r"^\d{11}$", str(parsed["phone"])):
                out["phone"] = str(parsed["phone"])
            if parsed.get("amount") is not None:
                try:
                    out["amount"] = float(parsed["amount"])
                except (TypeError, ValueError):
                    pass
            return out
    except Exception:
        pass
    return {}


def _run_step(step: "PlanStep", state: "UnicomAgentState") -> dict[str, Any]:
    action = step.get("action")
    auth = state.get("auth_context") or {}
    phone = _extract_phone(state)
    user_input = state.get("user_input") or ""
    llm_config = state.get("llm_config")

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
        entities = dict(state.get("confirmed_entities") or {})
        if phone:
            entities["phone"] = phone
        # 优先大模型提取金额等
        llm_entities = _extract_params_by_llm(user_input, llm_config)
        if llm_entities.get("phone"):
            entities["phone"] = llm_entities["phone"]
        if llm_entities.get("amount") is not None:
            entities["amount"] = llm_entities["amount"]
        if entities.get("amount") is None:
            amount = _extract_amount_by_rules(user_input)
            if amount is not None:
                entities["amount"] = amount
        return {"ok": True, "confirmed_entities": entities}

    if action == "execute_payment":
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
            amount = _extract_amount_by_rules(user_input)
        if amount is None or amount <= 0:
            return {"ok": False, "reason": "请提供有效缴费金额"}
        phone = phone or entities.get("phone")
        if not phone:
            return {"ok": False, "reason": "需要手机号"}
        return execute_payment(phone, float(amount), auth_context=auth)

    return {"ok": False, "reason": f"未知动作: {action}"}


def executor(state: "UnicomAgentState") -> "UnicomAgentState":
    """Executor 节点：执行 plan 中当前步骤。"""
    plan_obj = state.get("plan")
    if not plan_obj or not plan_obj.get("steps"):
        return {**state, "execution_error": {"hint": "无有效规划", "action_required": "REGENERATE_PLAN"}}

    idx = state.get("current_step_index", 0)
    steps = plan_obj["steps"]
    if idx >= len(steps):
        return {**state, "final_response": "处理完成", "should_end": True}

    step = steps[idx]
    if step.get("agent") != "Executor":
        return {**state, "current_step_index": idx + 1}

    result = _run_step(step, state)
    step_results = dict(state.get("step_results") or {})
    step_results[step.get("action", "step")] = result

    confirmed = dict(state.get("confirmed_entities") or {})
    if result.get("confirmed_entities"):
        confirmed.update(result["confirmed_entities"])

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

    return {
        **state,
        "step_results": step_results,
        "confirmed_entities": confirmed,
        "current_step_index": idx + 1,
        "execution_error": None,
    }
