# -*- coding: utf-8 -*-
"""
联通智能客服 - Reporter 应答 Agent

支持大模型生成自然语言回复；失败时使用模板回复。
"""

from __future__ import annotations

import json
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


def _template_response(intent: "IntentType", step_results: dict, err: dict | None) -> str:
    """模板回复（无 LLM 或 LLM 失败时）。"""
    if err:
        return err.get("hint", "处理遇到问题，请稍后再试。")
    if intent == "pay_bill":
        return _format_payment_response(step_results)
    if intent == "query_bill":
        return _format_bill_response(step_results)
    if intent == "query_balance":
        return _format_balance_response(step_results)
    if intent == "query_package":
        return "您可登录中国联通 APP 或拨打 10010 查询与变更套餐。"
    return "您好，我是联通智能客服。您可以问我：缴费、查账单、查余额、查套餐等。"


def _llm_response(
    intent: "IntentType",
    step_results: dict,
    user_input: str,
    config=None,
    retrieved_context: str | None = None,
) -> str | None:
    """大模型生成自然语言回复，可结合多路召回知识。"""
    from .llm import UnicomLLMConfig, chat
    cfg = config or UnicomLLMConfig()
    if not cfg.api_key and "api.openai.com" in cfg.base_url:
        return None
    sys_prompt = "你是联通智能客服。根据执行结果与参考知识，用一两句简洁、友好的中文回复用户，不要复述系统字段名。"
    data_str = json.dumps(step_results, ensure_ascii=False)
    user_msg = f"用户意图：{intent}\n用户原话：{user_input or ''}\n执行结果：{data_str}\n请直接给出回复内容（不要「回复：」等前缀）。"
    if (retrieved_context or "").strip():
        user_msg += f"\n\n参考知识（多路召回）：\n{retrieved_context.strip()}"
    try:
        content = chat(
            [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_msg}],
            config=cfg,
            model=cfg.model_reporter,
        )
        if content and len(content.strip()) > 0:
            return content.strip()
    except Exception:
        pass
    return None


def reporter(state: "UnicomAgentState") -> "UnicomAgentState":
    """Reporter 节点：优先大模型生成回复（可结合多路召回知识），失败则模板。"""
    intent = state.get("intent") or "general"
    step_results = state.get("step_results") or {}
    err = state.get("execution_error")
    user_input = state.get("user_input") or ""
    config = state.get("llm_config")
    retrieved_context = state.get("retrieved_context")
    memory_context = state.get("memory_context")
    if (memory_context or "").strip():
        retrieved_context = (retrieved_context or "").strip()
        retrieved_context = (retrieved_context + "\n\n" + memory_context.strip()).strip() if retrieved_context else memory_context.strip()

    # 敏感业务降级转接（Skill 统一管理）
    handoff_info = None
    try:
        from .skills import evaluate_handoff

        decision = evaluate_handoff(state)
        if decision.get("need_handoff"):
            handoff_info = decision
            text = decision.get("message") or "请求涉及敏感业务，已为您转接人工客服处理。"
        else:
            text = _llm_response(intent, step_results, user_input, config, retrieved_context)
            if not text:
                text = _template_response(intent, step_results, err)
    except Exception:
        text = _llm_response(intent, step_results, user_input, config, retrieved_context)
        if not text:
            text = _template_response(intent, step_results, err)

    # 写入长期记忆事件（双存储中的“事件日志”）
    try:
        from .memory import append_long_memory_event

        auth = state.get("auth_context") or {}
        append_long_memory_event(
            tenant_id=str(auth.get("tenant_id") or "UNICOM_PUBLIC"),
            user_id=str(auth.get("user_id") or "anonymous"),
            event={
                "intent": intent,
                "phone": str((state.get("confirmed_entities") or {}).get("phone") or auth.get("phone") or ""),
                "amount": (state.get("confirmed_entities") or {}).get("amount"),
                "user": user_input,
                "assistant": text,
                "ok": False if err else True,
            },
        )
    except Exception:
        pass

    return {
        **state,
        "final_response": text,
        "should_end": True,
        "handoff_info": handoff_info,
    }
