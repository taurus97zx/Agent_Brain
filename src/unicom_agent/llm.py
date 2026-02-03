# -*- coding: utf-8 -*-
"""
联通智能客服 - 大模型调用（OpenAI 兼容 API）

支持：OpenAI、Azure、Ollama、vLLM、通义千问等任意兼容 /v1/chat/completions 的服务。
通过环境变量或 UnicomLLMConfig 配置 base_url、api_key、模型名。
"""

from __future__ import annotations

import os
import json
import re
from typing import Any, Optional

# 可选：若未安装 openai，用 httpx 裸调
try:
    from openai import OpenAI
    from openai import AsyncOpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

_DEFAULT_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
_DEFAULT_KEY = os.environ.get("OPENAI_API_KEY", "")
_DEFAULT_MODEL = os.environ.get("UNICOM_LLM_MODEL", "gpt-3.5-turbo")


class UnicomLLMConfig:
    """LLM 配置，可从环境变量读取。"""
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        model_router: Optional[str] = None,
        model_planner: Optional[str] = None,
        model_executor: Optional[str] = None,
        model_reporter: Optional[str] = None,
        timeout: float = 30.0,
    ):
        base = (base_url or os.environ.get("OPENAI_API_BASE") or _DEFAULT_BASE).rstrip("/")
        self.base_url = base if base.endswith("/v1") else (base + "/v1")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or _DEFAULT_KEY
        self.timeout = timeout
        default_model = model or os.environ.get("UNICOM_LLM_MODEL") or _DEFAULT_MODEL
        self.model = default_model
        self.model_router = model_router or os.environ.get("UNICOM_LLM_MODEL_ROUTER") or default_model
        self.model_planner = model_planner or os.environ.get("UNICOM_LLM_MODEL_PLANNER") or default_model
        self.model_executor = model_executor or os.environ.get("UNICOM_LLM_MODEL_EXECUTOR") or default_model
        self.model_reporter = model_reporter or os.environ.get("UNICOM_LLM_MODEL_REPORTER") or default_model


def _get_client(config: UnicomLLMConfig) -> Any:
    if _HAS_OPENAI:
        return OpenAI(base_url=config.base_url, api_key=config.api_key, timeout=config.timeout)
    raise ImportError("请安装 openai: pip install openai")


def _get_async_client(config: UnicomLLMConfig) -> Any:
    if _HAS_OPENAI:
        return AsyncOpenAI(base_url=config.base_url, api_key=config.api_key, timeout=config.timeout)
    raise ImportError("请安装 openai: pip install openai")


def chat(
    messages: list[dict[str, str]],
    config: Optional[UnicomLLMConfig] = None,
    model: Optional[str] = None,
) -> str:
    """
    同步调用 chat completions，返回 content 字符串。
    """
    cfg = config or UnicomLLMConfig()
    client = _get_client(cfg)
    resp = client.chat.completions.create(
        model=model or cfg.model,
        messages=messages,
        temperature=0.1,
        max_tokens=1024,
    )
    content = resp.choices[0].message.content if resp.choices else ""
    return (content or "").strip()


async def chat_async(
    messages: list[dict[str, str]],
    config: Optional[UnicomLLMConfig] = None,
    model: Optional[str] = None,
) -> str:
    """异步调用 chat completions。"""
    cfg = config or UnicomLLMConfig()
    client = _get_async_client(cfg)
    resp = await client.chat.completions.create(
        model=model or cfg.model,
        messages=messages,
        temperature=0.1,
        max_tokens=1024,
    )
    content = resp.choices[0].message.content if resp.choices else ""
    return (content or "").strip()


def parse_json_from_content(content: str) -> Optional[dict | list]:
    """从模型输出中解析 JSON（允许前后有说明文字）。"""
    content = (content or "").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    for pattern in (r"```(?:json)?\s*([\s\S]*?)```", r"(\{[\s\S]*\})", r"(\[[\s\S]*\])"):
        m = re.search(pattern, content)
        if m:
            raw = m.group(1).strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                continue
    return None


def parse_and_validate(content: str, model_class: type, *, as_list_item: bool = False) -> Any:
    """
    解析 JSON 并用 Pydantic 校验，防止错误 schema。
    - content: 模型原始输出
    - model_class: Pydantic BaseModel 或用于 list 的单元素模型
    - as_list_item: True 时 content 解析为 list，对每项做 model_class 校验，返回 list[model]
    校验失败返回 None，调用方回退到规则/模板。
    """
    try:
        from pydantic import ValidationError
    except ImportError:
        return None
    raw = parse_json_from_content(content)
    if raw is None:
        return None
    try:
        if as_list_item:
            if not isinstance(raw, list):
                return None
            return [model_class.model_validate(item) for item in raw]
        return model_class.model_validate(raw)
    except (ValidationError, TypeError, ValueError):
        return None
