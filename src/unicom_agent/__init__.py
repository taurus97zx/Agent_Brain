# -*- coding: utf-8 -*-
"""
联通智能客服缴费 - 多智能体系统

组件：
- Router：意图分类（确定性）
- Planner：任务规划（大模型一次或规则）
- Executor：执行缴费/查账等（小模型+权限校验）
- Reporter：生成回复（中模型或模板）
"""

from .state import (
    AuthContext,
    ConfirmedEntities,
    IntentType,
    Plan,
    UnicomAgentState,
)
from .workflow import build_workflow, get_unicom_agent
from .llm import UnicomLLMConfig

__all__ = [
    "UnicomAgentState",
    "IntentType",
    "Plan",
    "AuthContext",
    "ConfirmedEntities",
    "build_workflow",
    "get_unicom_agent",
    "UnicomLLMConfig",
]
