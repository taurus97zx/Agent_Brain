# 联通智能客服缴费 - 多智能体系统

基于 **Router + Planner + Executor + Reporter** 的联通智能客服缴费多智能体，与仓库内 `docs/04_multi_agent_orche` 设计一致：消息传递、State Table、权限不可欺骗、Error Adapter。

## 架构

| 组件 | 职责 | 模型/实现 |
|------|------|-----------|
| **Router** | 意图分类 | 规则/小模型（确定性） |
| **Planner** | 任务规划 | 大模型一次或规则 |
| **Executor** | 参数提取 + 缴费/查账 API | 小模型 + 权限校验 |
| **Reporter** | 生成回复 | 中模型或模板 |

- **状态**：`UnicomAgentState`（消息传递 + State Table，已确认实体单独维护）
- **权限**：缴费等写操作由 `auth_context.permissions` 校验，不可由用户自然语言伪造
- **失败**：Executor 失败通过 Error Adapter 转为业务态错误，再交给 Reporter 回复

## 意图

- `pay_bill`：缴费
- `query_bill`：查账单
- `query_balance`：查余额
- `query_package`：查套餐
- `general`：通用客服

## 安装与运行

**方式一：从项目根目录（推荐）**

```bash
cd Agent_Brain
pip install -r src/unicom_agent/requirements.txt
python run_unicom_agent.py "我要交 50 元话费"
python run_unicom_agent.py "查一下我的账单"
python run_unicom_agent.py "余额还有多少"
```

**方式二：从 src 目录**

```bash
cd Agent_Brain/src
pip install -r unicom_agent/requirements.txt
python -m unicom_agent.run "我要交 50 元话费"
python -m unicom_agent.run "查一下我的账单"
```

若报 `ModuleNotFoundError: No module named 'unicom_agent'`，请使用方式一或确保当前目录为 `src`。

## 代码结构

```
unicom_agent/
├── state.py      # UnicomAgentState、Plan、AuthContext 等
├── router.py     # 意图分类
├── planner.py    # 规划生成
├── executor.py   # 执行 + 权限校验
├── reporter.py   # 最终回复
├── workflow.py   # LangGraph 编排
├── run.py        # 命令行入口
├── tools/
│   └── billing.py  # 查账/缴费工具（可替换为真实 BSS 接口）
├── requirements.txt
└── README.md
```

## 扩展示例

- **Router**：将 `classify_intent` 换为调用 Qwen-7B 等小模型做分类
- **Planner**：将 `INTENT_PLANS` 换为一次大模型调用生成 `steps`
- **Executor**：将 `tools/billing.py` 换为 httpx 调用真实计费/BSS 接口
- **租户隔离**：在 Router 前根据 `auth_context.tenant_id` 选择规则集/知识库命名空间（参考 `docs/04_multi_agent_orche` 中的 `rule_scope`、`kb_namespace`）
