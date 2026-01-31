# -*- coding: utf-8 -*-
"""
联通智能客服缴费 - 从项目根目录运行入口

用法（在 Agent_Brain 目录下）：
  python run_unicom_agent.py
  python run_unicom_agent.py "我要交 50 元话费"
  python run_unicom_agent.py "查一下我的账单"
"""
from __future__ import annotations

import os
import sys

# 将 src 加入路径，保证从项目根目录也能找到 unicom_agent
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if __name__ == "__main__":
    from unicom_agent.run import main
    main()
