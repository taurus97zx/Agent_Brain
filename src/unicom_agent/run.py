# -*- coding: utf-8 -*-
"""
联通智能客服缴费 - 本地运行入口

示例：
  python -m unicom_agent.run "我要交 50 元话费"
  python -m unicom_agent.run "查一下我的账单"
"""

from __future__ import annotations

import json
import sys


def main():
    from .workflow import get_unicom_agent

    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "我想查余额"
    auth_context = {
        "user_id": "u_demo",
        "phone": "13800138000",
        "tenant_id": "UNICOM_PUBLIC",
        "permissions": ["PAY_BILL", "QUERY_BILL", "QUERY_BALANCE"],
    }

    initial_state = {
        "messages": [],
        "user_input": user_input,
        "auth_context": auth_context,
        "confirmed_entities": {},
    }

    app = get_unicom_agent()
    result = app.invoke(initial_state)

    print("--- 意图 ---")
    print(result.get("intent", ""))
    print("--- 回复 ---")
    print(result.get("final_response", ""))
    if result.get("step_results"):
        print("--- 步骤结果（调试） ---")
        print(json.dumps(result["step_results"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
