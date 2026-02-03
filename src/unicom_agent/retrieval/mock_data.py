# -*- coding: utf-8 -*-
"""
联通智能客服 - 模拟数据：向量库、知识图谱、规则文档

用于多路召回检索，提升召回率。实际环境可替换为真实 ES/Milvus/Neo4j 等。
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

# ----- 1. 模拟向量库文档（FAQ / 业务说明） -----
# 模拟 embedding：用文本 hash 生成固定维度的伪向量，便于复现
def _mock_embedding(text: str, dim: int = 64) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    nums = [int(h[i : i + 2], 16) / 255.0 for i in range(0, min(len(h), dim * 2), 2)]
    while len(nums) < dim:
        nums.extend([int(h[i % len(h)], 16) / 15.0 for i in range(len(nums), len(nums) + dim - len(nums))])
    norm = math.sqrt(sum(x * x for x in nums[:dim]))
    return [x / (norm or 1) for x in nums[:dim]]


VECTOR_DB_CHUNKS = [
    {"id": "vec_1", "text": "用户可以通过中国联通APP、网上营业厅、10010热线或线下营业厅进行话费缴费。支持银行卡、微信、支付宝。", "source": "缴费说明"},
    {"id": "vec_2", "text": "缴费金额需大于0元，单笔缴费上限一般为5000元，具体以页面提示为准。缴费后即时到账。", "source": "缴费规则"},
    {"id": "vec_3", "text": "查询账单可登录中国联通APP，在「服务-查询-话费账单」中查看月账单、欠费金额及明细。", "source": "账单查询"},
    {"id": "vec_4", "text": "欠费停机后需先缴清欠费才能恢复通信。欠费超过一定期限可能影响信用与复机。", "source": "欠费说明"},
    {"id": "vec_5", "text": "账户余额指当前可用预存款，可用于抵扣月租、流量、语音等费用。可在APP「我的-余额」查看。", "source": "余额说明"},
    {"id": "vec_6", "text": "套餐包含月租、流量、语音等内容。变更套餐次月生效，当月按原套餐计费。", "source": "套餐说明"},
    {"id": "vec_7", "text": "流量包分为月包、季包、年包等，超出套餐流量按0.1元/MB计费或可订购加油包。", "source": "流量规则"},
    {"id": "vec_8", "text": "实名制用户可通过本机拨打10010或登录APP验证身份后办理缴费、查账单、改套餐等业务。", "source": "办理须知"},
    {"id": "vec_9", "text": "缴费记录可在「我的-消费记录」中查询。发票可在中国联通APP内申请电子发票。", "source": "缴费记录"},
    {"id": "vec_10", "text": "若缴费失败，请检查网络、支付方式余额或银行卡限额。重复扣款可联系客服核实退费。", "source": "异常处理"},
]

# 为每条生成模拟向量
for c in VECTOR_DB_CHUNKS:
    c["embedding"] = _mock_embedding(c["text"])


# ----- 2. 模拟知识图谱（实体 + 关系） -----
# 格式：节点 id, label, 属性；边 head, relation, tail
KG_ENTITIES = [
    {"id": "e_缴费", "label": "业务", "name": "缴费", "keywords": ["缴费", "交费", "充值", "付款", "还款"]},
    {"id": "e_账单", "label": "业务", "name": "账单", "keywords": ["账单", "欠费", "话费清单", "消费明细"]},
    {"id": "e_余额", "label": "业务", "name": "余额", "keywords": ["余额", "剩余", "预存款"]},
    {"id": "e_套餐", "label": "业务", "name": "套餐", "keywords": ["套餐", "月租", "资费", "流量", "语音"]},
    {"id": "e_APP", "label": "渠道", "name": "中国联通APP", "keywords": ["APP", "手机营业厅"]},
    {"id": "e_10010", "label": "渠道", "name": "10010", "keywords": ["10010", "热线", "客服"]},
    {"id": "e_营业厅", "label": "渠道", "name": "营业厅", "keywords": ["营业厅", "线下"]},
    {"id": "e_月租", "label": "费用", "name": "月租", "keywords": ["月租", "月费"]},
    {"id": "e_流量", "label": "资源", "name": "流量", "keywords": ["流量", "上网"]},
    {"id": "e_停机", "label": "状态", "name": "欠费停机", "keywords": ["停机", "欠费停机", "复机"]},
]

KG_RELATIONS = [
    {"head": "e_缴费", "relation": "涉及", "tail": "e_账单", "weight": 1.0},
    {"head": "e_缴费", "relation": "涉及", "tail": "e_余额", "weight": 0.9},
    {"head": "e_缴费", "relation": "通过", "tail": "e_APP", "weight": 0.8},
    {"head": "e_缴费", "relation": "通过", "tail": "e_10010", "weight": 0.8},
    {"head": "e_账单", "relation": "关联", "tail": "e_余额", "weight": 0.9},
    {"head": "e_账单", "relation": "包含", "tail": "e_月租", "weight": 0.85},
    {"head": "e_套餐", "relation": "包含", "tail": "e_流量", "weight": 0.9},
    {"head": "e_套餐", "relation": "包含", "tail": "e_月租", "weight": 0.9},
    {"head": "e_欠费", "relation": "导致", "tail": "e_停机", "weight": 1.0},
    {"head": "e_余额", "relation": "抵扣", "tail": "e_月租", "weight": 0.85},
]

# 补充「欠费」实体
KG_ENTITIES.append({"id": "e_欠费", "label": "状态", "name": "欠费", "keywords": ["欠费", "欠款"]})


# ----- 3. 模拟规则文档 -----
RULE_DOCS = [
    {
        "id": "rule_1",
        "title": "缴费业务规则",
        "content": "缴费仅支持实名用户；单笔金额0.01-5000元；缴费后即时到账；重复缴费可申请退费。",
        "keywords": ["缴费", "金额", "到账", "退费"],
        "scope": "pay_bill",
    },
    {
        "id": "rule_2",
        "title": "账单查询规则",
        "content": "可查询当前月及历史月账单；欠费用户需先缴清欠费方可办理部分业务；账单明细保留12个月。",
        "keywords": ["账单", "欠费", "查询", "明细"],
        "scope": "query_bill",
    },
    {
        "id": "rule_3",
        "title": "余额与停机规则",
        "content": "余额不足可能导致停机；欠费停机后缴清欠费一般24小时内复机；余额不可提现。",
        "keywords": ["余额", "停机", "复机", "欠费"],
        "scope": "query_balance",
    },
    {
        "id": "rule_4",
        "title": "套餐变更规则",
        "content": "套餐变更次月生效；当月按原套餐计费；升级套餐可立即生效，降级次月生效。",
        "keywords": ["套餐", "变更", "生效", "月租"],
        "scope": "query_package",
    },
    {
        "id": "rule_5",
        "title": "身份校验规则",
        "content": "办理缴费、查账单、改套餐等需验证本机或登录态；不可代他人办理敏感业务。",
        "keywords": ["身份", "校验", "登录", "办理"],
        "scope": "general",
    },
]


def get_vector_chunks() -> list[dict[str, Any]]:
    """返回带 embedding 的向量库文档（只读）。"""
    return list(VECTOR_DB_CHUNKS)


def get_kg_entities() -> list[dict[str, Any]]:
    """返回知识图谱实体列表。"""
    return list(KG_ENTITIES)


def get_kg_relations() -> list[dict[str, Any]]:
    """返回知识图谱关系列表。"""
    return list(KG_RELATIONS)


def get_rule_docs() -> list[dict[str, Any]]:
    """返回规则文档列表。"""
    return list(RULE_DOCS)
