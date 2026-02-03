# -*- coding: utf-8 -*-
"""
联通智能客服 - 大模型输出 JSON 的 Pydantic Schema 校验

防止大模型生成错误或不完整的 JSON，校验失败时回退到规则/模板。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, field_validator


# ----- Router 意图分类 -----
IntentLiteral = Literal["pay_bill", "query_bill", "query_balance", "query_package", "general"]


class IntentOutput(BaseModel):
    """Router 输出：仅一个意图标签。"""
    intent: IntentLiteral

    @field_validator("intent", mode="before")
    @classmethod
    def normalize_intent(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip().lower()
            if v in ("pay_bill", "query_bill", "query_balance", "query_package", "general"):
                return v
        raise ValueError("intent 必须是 pay_bill | query_bill | query_balance | query_package | general")


# ----- Planner 规划步骤 -----
AgentLiteral = Literal["Executor", "Reporter"]
ActionLiteral = Literal[
    "validate_user", "query_bill", "query_balance", "extract_params", "execute_payment", "respond"
]


class PlanStepSchema(BaseModel):
    """单步规划。"""
    agent: AgentLiteral
    action: ActionLiteral

    @field_validator("agent", mode="before")
    @classmethod
    def normalize_agent(cls, v: str) -> str:
        if isinstance(v, str) and v.strip() in ("Executor", "Reporter"):
            return v.strip()
        raise ValueError("agent 必须是 Executor 或 Reporter")

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v: str) -> str:
        allowed = ("validate_user", "query_bill", "query_balance", "extract_params", "execute_payment", "respond")
        if isinstance(v, str) and v.strip() in allowed:
            return v.strip()
        raise ValueError(f"action 必须是 {allowed} 之一")


class PlanOutputSchema(BaseModel):
    """Planner 输出：步骤数组（根为对象时用）。"""
    steps: list[PlanStepSchema]

    @field_validator("steps")
    @classmethod
    def steps_non_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("steps 不能为空")
        return v


def validate_plan_steps(raw: list) -> list[PlanStepSchema]:
    """校验并返回步骤列表；LLM 直接返回数组时使用。"""
    if not raw:
        raise ValueError("steps 不能为空")
    return [PlanStepSchema.model_validate(item) for item in raw]


# ----- Executor 参数提取 -----
class ExtractedParamsSchema(BaseModel):
    """Executor 参数提取输出：手机号、金额。"""
    phone: Optional[str] = None
    amount: Optional[float] = None

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str | None) -> Optional[str]:
        if v is None or (isinstance(v, str) and v.strip().lower() in ("null", "")):
            return None
        if isinstance(v, str):
            s = v.strip()
            if len(s) == 11 and s.isdigit():
                return s
        if isinstance(v, (int, float)) and len(str(int(v))) == 11:
            return str(int(v))
        return None

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v: str | int | float | None) -> Optional[float]:
        if v is None or (isinstance(v, str) and v.strip().lower() in ("null", "")):
            return None
        try:
            f = float(v)
            if f < 0:
                return None
            return round(f, 2)
        except (TypeError, ValueError):
            return None
