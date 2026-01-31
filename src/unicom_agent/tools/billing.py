# -*- coding: utf-8 -*-
"""
联通智能客服 - 缴费/账单工具（Executor 调用）

权限校验在 Executor 层做不可欺骗校验，此处仅做业务逻辑。
"""

from __future__ import annotations

from typing import Any, Optional


# 模拟数据（实际对接 BSS/计费系统）
_MOCK_BILLS: dict[str, list[dict]] = {}
_MOCK_BALANCE: dict[str, float] = {}


def validate_user(phone: str, auth_context: Optional[dict] = None) -> dict[str, Any]:
    """
    校验用户身份（与登录态一致）。
    auth_context 由系统注入，不可由用户自然语言伪造。
    """
    if auth_context and auth_context.get("phone") and phone != auth_context["phone"]:
        return {"ok": False, "reason": "手机号与登录账号不一致"}
    if not phone or len(phone) != 11:
        return {"ok": False, "reason": "手机号格式错误"}
    return {"ok": True, "phone": phone}


def query_bill(phone: str, month: Optional[str] = None) -> dict[str, Any]:
    """查询账单。month 格式 YYYY-MM，不传则查当前月。"""
    global _MOCK_BILLS
    key = f"{phone}:{month or 'current'}"
    if key not in _MOCK_BILLS:
        _MOCK_BILLS[key] = [
            {"item": "月租", "amount": 59.0},
            {"item": "流量", "amount": 0.0},
            {"item": "语音", "amount": 10.0},
        ]
    total = sum(b["amount"] for b in _MOCK_BILLS[key])
    return {
        "ok": True,
        "phone": phone,
        "month": month or "当前月",
        "items": _MOCK_BILLS[key],
        "total": round(total, 2),
    }


def query_balance(phone: str) -> dict[str, Any]:
    """查询账户余额。"""
    global _MOCK_BALANCE
    if phone not in _MOCK_BALANCE:
        _MOCK_BALANCE[phone] = 0.0
    return {"ok": True, "phone": phone, "balance": _MOCK_BALANCE[phone]}


def execute_payment(
    phone: str,
    amount: float,
    bill_id: Optional[str] = None,
    auth_context: Optional[dict] = None,
) -> dict[str, Any]:
    """
    执行缴费。权限 WRITE_OFF_ARREARS 等由 Executor 校验，此处不抹账。
    """
    if amount <= 0:
        return {"ok": False, "reason": "金额必须大于 0"}
    # 模拟扣款成功
    global _MOCK_BALANCE
    if phone not in _MOCK_BALANCE:
        _MOCK_BALANCE[phone] = 0.0
    _MOCK_BALANCE[phone] -= amount
    return {
        "ok": True,
        "phone": phone,
        "amount": amount,
        "bill_id": bill_id,
        "message": f"缴费成功，金额 {amount} 元",
    }
