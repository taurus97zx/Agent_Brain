# -*- coding: utf-8 -*-
"""
联通智能客服 - Planner 规划 Agent

设计原则：
- Planner 只生成 Plan，不执行
- 大模型只允许调用一次（或规则/小模型生成步骤）
- 输出 plan_status: FINAL、final_answer_ready、confidence
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .state import IntentType, Plan, PlanStep, UnicomAgentState


# 意图 -> 固定步骤（可替换为一次 LLM 调用生成）
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
    "general": [
        {"agent": "Reporter", "action": "respond"},
    ],
}


def build_plan(intent: "IntentType") -> "Plan":
    """根据意图生成不可变 Plan。"""
    steps_raw = INTENT_PLANS.get(intent, INTENT_PLANS["general"])
    steps: list[PlanStep] = [
        {"agent": s["agent"], "action": s["action"]}  # type: ignore
        for s in steps_raw
    ]
    return {
        "plan_id": f"p_{uuid.uuid4().hex[:8]}",
        "intent": intent,
        "steps": steps,
        "plan_status": "FINAL",
        "final_answer_ready": False,
        "confidence": 0.95,
    }


def plan(state: "UnicomAgentState") -> "UnicomAgentState":
    """
    Planner 节点：根据 state["intent"] 生成 Plan，写入 state["plan"]。
    """
    intent = state.get("intent") or "general"
    plan = build_plan(intent)
    return {
        **state,
        "plan": plan,
        "current_step_index": 0,
        "step_results": {},
    }
