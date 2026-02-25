
### 通过 Literal 限制 Planner 只能在预定义的工具集中选择，并强制要求任务 ID 和依赖关系

    from typing import List, Literal, Dict, Any, Optional
    from pydantic import BaseModel, Field, root_validator

    # 1. 定义所有合法的原子操作（Executor 能够识别的指令）
    ActionType = Literal[
        "QUERY_BALANCE",      # 查询余额
        "CHECK_ARREARS",     # 欠费校验
        "CONFLICT_DETECTION", # 冲突检查
        "SUBMIT_ORDER",       # 提交办理
        "WRITE_BACK_RESULT",  # 结果回写
        "ASK_USER"            # 反问用户缺失信息
    ]

    class Task(BaseModel):
        task_id: int
        action: ActionType
        description: str
        args: Dict[str, Any] = Field(default_factory=dict)
        depends_on: List[int] = Field(default_factory=list, description="依赖的任务ID列表")

    class BusinessPlan(BaseModel):
        plan_id: str
        steps: List[Task]

        # 核心逻辑：交叉验证（防跳步）
        @root_validator
        def validate_business_logic(cls, values):
            steps = values.get('steps', [])
            actions = [s.action for s in steps]
            
            # 约束1：如果存在“提交办理”，则之前必须有“冲突检查”
            if "SUBMIT_ORDER" in actions:
                submit_idx = actions.index("SUBMIT_ORDER")
                if "CONFLICT_DETECTION" not in actions[:submit_idx]:
                    raise ValueError("逻辑错误：提交办理前必须完成冲突检查（CONFLICT_DETECTION）")
            
            # 约束2：如果存在“冲突检查”，之前必须有“欠费校验”
            if "CONFLICT_DETECTION" in actions:
                conflict_idx = actions.index("CONFLICT_DETECTION")
                if "CHECK_ARREARS" not in actions[:conflict_idx]:
                    raise ValueError("逻辑错误：冲突检查前必须完成欠费校验（CHECK_ARREARS）")

            # 约束3：检查 ID 依赖是否存在环或引用不存在的任务
            existing_ids = {s.task_id for s in steps}
            for s in steps:
                for dep in s.depends_on:
                    if dep not in existing_ids:
                        raise ValueError(f"任务 {s.task_id} 依赖的 ID {dep} 不存在")
            
            return values