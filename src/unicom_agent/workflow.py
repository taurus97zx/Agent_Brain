# -*- coding: utf-8 -*-
"""
联通智能客服缴费 - LangGraph 工作流编排

流程：Router -> Retrieve（多路召回）-> Planner -> Executor (循环) -> Reporter -> END
- Router：意图分类
- Retrieve：向量 + KG + 规则三路召回，合并去重排序，写入 retrieved_context
- Planner：生成 Plan（可结合 retrieved_context）
- Executor：按步执行，权限校验，Error Adapter
- Reporter：生成最终回复（可结合 retrieved_context）
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from .executor import executor
from .planner import plan
from .reporter import reporter
from .retrieve_node import retrieve
from .router import route
from .state import UnicomAgentState


def _after_executor(state: UnicomAgentState) -> Literal["executor", "reporter"]:
    """Executor 之后：下一步是 Reporter 则去 reporter，否则继续 executor。"""
    if state.get("should_end"):
        return "reporter"
    plan_obj = state.get("plan")
    idx = state.get("current_step_index", 0)
    if not plan_obj or not plan_obj.get("steps"):
        return "reporter"
    steps = plan_obj["steps"]
    if idx >= len(steps):
        return "reporter"
    next_step = steps[idx]
    if next_step.get("agent") == "Reporter":
        return "reporter"
    return "executor"


def build_workflow() -> StateGraph:
    """构建联通客服缴费多智能体工作流。"""
    workflow: StateGraph = StateGraph(UnicomAgentState)

    workflow.add_node("router", route)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("planner", plan)
    workflow.add_node("executor", executor)
    workflow.add_node("reporter", reporter)

    workflow.add_edge(START, "router")
    workflow.add_edge("router", "retrieve")
    workflow.add_edge("retrieve", "planner")
    workflow.add_edge("planner", "executor")
    workflow.add_conditional_edges("executor", _after_executor, {"executor": "executor", "reporter": "reporter"})
    workflow.add_edge("reporter", END)

    return workflow


def get_unicom_agent():
    """返回编译后的联通智能客服 Agent（可 invoke/stream）。"""
    graph = build_workflow()
    return graph.compile()
