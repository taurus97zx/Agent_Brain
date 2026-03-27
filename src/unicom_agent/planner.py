# -*- coding: utf-8 -*-
"""
联通智能客服 - Planner 规划 Agent

支持大模型一次调用生成规划步骤；失败时使用预设规则规划。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .state import IntentType, Plan, PlanStep, UnicomAgentState

# 规则回退：意图 -> 步骤
INTENT_PLANS: dict["IntentType", list[dict[str, Any]]] = {
    "pay_bill": [
        {"agent": "Executor", "action": "validate_user"},
        {"agent": "Executor", "action": "query_bill"},
        {"agent": "Executor", "action": "extract_params"},
        {"agent": "Executor", "action": "execute_payment"},
        {"agent": "Reporter", "action": "respond"},
    ],
    "query_bill": [
        {"agent": "Executor", "action": "validate_user"},
        {"agent": "Executor", "action": "query_bill"},
        {"agent": "Reporter", "action": "respond"},
    ],
    "query_balance": [
        {"agent": "Executor", "action": "validate_user"},
        {"agent": "Executor", "action": "query_balance"},
        {"agent": "Reporter", "action": "respond"},
    ],
    "query_package": [
        {"agent": "Executor", "action": "validate_user"},
        {"agent": "Reporter", "action": "respond"},
    ],
    "general": [{"agent": "Reporter", "action": "respond"}],
}

VALID_ACTIONS = {"validate_user", "query_bill", "query_balance", "extract_params", "execute_payment", "respond"}
VALID_AGENTS = {"Executor", "Reporter"}


def _build_plan_from_steps(intent: "IntentType", steps_raw: list[dict]) -> "Plan":
    steps: list[PlanStep] = []
    for s in steps_raw:
        agent = s.get("agent") or s.get("agent_name")
        action = s.get("action")
        if agent not in VALID_AGENTS or action not in VALID_ACTIONS:
            continue
        steps.append({"agent": agent, "action": action})  # type: ignore
    if not steps:
        steps_raw = INTENT_PLANS.get(intent, INTENT_PLANS["general"])
        steps = [{"agent": s["agent"], "action": s["action"]} for s in steps_raw]  # type: ignore
    return {
        "plan_id": f"p_{uuid.uuid4().hex[:8]}",
        "intent": intent,
        "steps": steps,
        "plan_status": "FINAL",
        "final_answer_ready": False,
        "confidence": 0.95,
    }


def _plan_by_rules(intent: "IntentType") -> "Plan":
    steps_raw = INTENT_PLANS.get(intent, INTENT_PLANS["general"])
    steps: list[PlanStep] = [{"agent": s["agent"], "action": s["action"]} for s in steps_raw]  # type: ignore
    return {
        "plan_id": f"p_{uuid.uuid4().hex[:8]}",
        "intent": intent,
        "steps": steps,
        "plan_status": "FINAL",
        "final_answer_ready": False,
        "confidence": 0.95,
    }


def _plan_by_llm(
    intent: "IntentType",
    user_input: str,
    config=None,
    retrieved_context: str | None = None,
) -> "Plan":
    from .llm import UnicomLLMConfig, chat, parse_json_from_content
    from .schemas import PlanStepSchema, validate_plan_steps
    from pydantic import ValidationError
    cfg = config or UnicomLLMConfig()
    sys_prompt = """你是联通智能客服的任务规划器。根据用户意图，输出执行步骤的 JSON 数组。
每个元素必须：{"agent": "Executor" 或 "Reporter", "action": "动作"}。
动作只能是：validate_user, query_bill, query_balance, extract_params, execute_payment, respond。
只输出 JSON 数组，不要其他说明。"""
    user_msg = f"意图：{intent}\n用户输入：{user_input or ''}\n请输出步骤 JSON 数组。"
    if (retrieved_context or "").strip():
        user_msg += f"\n\n参考知识（多路召回）：\n{retrieved_context.strip()}"
    try:
        content = chat(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
            config=cfg,
            model=cfg.model_planner,
        )
        parsed = parse_json_from_content(content)
        if isinstance(parsed, list) and parsed:
            steps_validated = validate_plan_steps(parsed)
            steps_raw = [{"agent": s.agent, "action": s.action} for s in steps_validated]
            return _build_plan_from_steps(intent, steps_raw)
        if isinstance(parsed, dict) and parsed.get("steps"):
            steps_validated = validate_plan_steps(parsed["steps"])
            steps_raw = [{"agent": s.agent, "action": s.action} for s in steps_validated]
            return _build_plan_from_steps(intent, steps_raw)
    except (ValidationError, ValueError, Exception):
        pass
    return _plan_by_rules(intent)


def build_plan(
    intent: "IntentType",
    user_input: str = "",
    use_llm: bool = True,
    config=None,
    retrieved_context: str | None = None,
) -> "Plan":
    """生成 Plan。use_llm 且配置可用时用大模型，否则规则。retrieved_context 来自多路召回。"""
    if use_llm and config:
        return _plan_by_llm(intent, user_input, config, retrieved_context)
    if use_llm:
        from .llm import UnicomLLMConfig
        return _plan_by_llm(intent, user_input, UnicomLLMConfig(), retrieved_context)
    return _plan_by_rules(intent)


def plan(state: "UnicomAgentState") -> "UnicomAgentState":
    """Planner 节点：根据 intent 生成 Plan，可结合多路召回上下文。"""
    intent = state.get("intent") or "general"
    user_input = state.get("user_input") or ""
    config = state.get("llm_config")
    retrieved_context = state.get("retrieved_context")
    memory_context = state.get("memory_context")
    if (memory_context or "").strip():
        retrieved_context = (retrieved_context or "").strip()
        retrieved_context = (retrieved_context + "\n\n" + memory_context.strip()).strip() if retrieved_context else memory_context.strip()
    plan_obj = build_plan(intent, user_input, use_llm=True, config=config, retrieved_context=retrieved_context)
    return {
        **state,
        "plan": plan_obj,
        "current_step_index": 0,
        "step_results": {},
    }
