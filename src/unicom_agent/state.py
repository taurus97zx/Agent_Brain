# -*- coding: utf-8 -*-
"""
联通智能客服缴费多智能体 - 共享状态定义

采用消息传递 + State Table 设计：
- 不直接传递全量历史，由 Orchestrator 维护状态表
- 记录已确认的实体信息（手机号、金额、账单ID等）
- 每一轮只将更新后的 State 传给下一个 Agent
"""

from typing import TypedDict, Annotated, Literal, Optional, Any
from langgraph.graph.message import add_messages


# 用户意图类型（Router 输出）
IntentType = Literal[
    "pay_bill",       # 缴费
    "query_bill",     # 查账单
    "query_balance",  # 查余额
    "query_package",  # 查套餐
    "general",        # 通用客服
]

# 规划步骤中的执行动作
StepAction = Literal[
    "extract_params",
    "validate_user",
    "query_bill",
    "query_balance",
    "execute_payment",
    "respond",
]


class PlanStep(TypedDict, total=False):
    """Planner 输出的单步"""
    agent: Literal["Executor", "Reporter"]
    action: StepAction
    tool: Optional[str]
    depends_on: Optional[list[str]]


class Plan(TypedDict, total=False):
    """Planner 输出：意图不可变"""
    plan_id: str
    intent: IntentType
    steps: list[PlanStep]
    plan_status: Literal["DRAFT", "FINAL"]
    final_answer_ready: bool
    confidence: float


class AuthContext(TypedDict, total=False):
    """鉴权上下文（来自登录态，非用户自然语言）"""
    user_id: str
    phone: str
    tenant_id: str
    permissions: list[str]


class ConfirmedEntities(TypedDict, total=False):
    """已确认的实体（State Table）"""
    phone: str
    amount: float
    bill_id: str
    package_name: str


class UnicomAgentState(TypedDict, total=False):
    """多智能体共享状态"""
    # 输入与路由
    messages: Annotated[list, add_messages]
    user_input: str
    intent: IntentType
    auth_context: AuthContext

    # 规划与执行
    plan: Plan
    current_step_index: int
    step_results: dict[str, Any]
    execution_error: Optional[dict]  # Error Adapter 后的业务态错误

    # 状态表（短期记忆）
    confirmed_entities: ConfirmedEntities

    # 输出
    final_response: str
    should_end: bool
