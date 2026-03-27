# -*- coding: utf-8 -*-
"""
联通智能客服缴费 - 本地运行入口

示例（在 src 目录下）：
  python -m unicom_agent.run "我要交 50 元话费"
  python -m unicom_agent.run "查一下我的账单"

或从项目根目录：
  python run_unicom_agent.py "我要交 50 元话费"
"""

from __future__ import annotations

import json
import os
import sys
import argparse


def main():
    # 若作为脚本直接运行（python run.py），确保包可被找到
    if __name__ == "__main__" and "__file__" in dir():
        _pkg_dir = os.path.dirname(os.path.abspath(__file__))
        _src = os.path.dirname(_pkg_dir)
        if _src not in sys.path:
            sys.path.insert(0, _src)

    try:
        from .workflow import get_unicom_agent
    except ImportError as e:
        print("导入失败:", e)
        print("请先安装依赖: pip install -r src/unicom_agent/requirements.txt")
        print("并从项目根目录运行: python run_unicom_agent.py \"缴费50元\"")
        print("或进入 src 目录运行: python -m unicom_agent.run \"缴费50元\"")
        sys.exit(1)

    from .llm import UnicomLLMConfig

    parser = argparse.ArgumentParser(description="联通智能客服 Agent 运行入口")
    parser.add_argument("query", nargs="*", help="用户输入内容")
    parser.add_argument(
        "--debug-handoff",
        action="store_true",
        help="输出降级转接调试信息（handoff_info）",
    )
    args = parser.parse_args()

    user_input = " ".join(args.query).strip() if args.query else "我想查余额"
    auth_context = {
        "user_id": "u_demo",
        "phone": "17660408875",
        "tenant_id": "UNICOM_PUBLIC",
        "permissions": ["PAY_BILL", "QUERY_BILL", "QUERY_BALANCE"],
    }
    # 大模型配置：从环境变量读取 OPENAI_API_BASE / OPENAI_API_KEY / UNICOM_LLM_MODEL
    llm_config = UnicomLLMConfig()

    initial_state = {
        "messages": [],
        "user_input": user_input,
        "auth_context": auth_context,
        "confirmed_entities": {},
        "llm_config": llm_config,
    }

    app = get_unicom_agent()
    result = app.invoke(initial_state)

    print("--- 意图 ---")
    print(result.get("intent", ""))
    print("--- 回复 ---")
    print(result.get("final_response", ""))
    if args.debug_handoff:
        print("--- 转接调试 ---")
        print(json.dumps(result.get("handoff_info"), ensure_ascii=False, indent=2))
    if result.get("step_results"):
        print("--- 步骤结果（调试） ---")
        print(json.dumps(result["step_results"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
