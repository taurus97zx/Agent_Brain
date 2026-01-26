


![alt text](image-1.png)

执行器有一个设计是：
串行：任务之间**存在依赖**。例如：任务B（总结文章）必须等任务A（下载文章）完成后才能开始。
并行：任务之间**没有依赖关系**。例如：同时搜索“百度的股价”和“腾讯的股价”





 相似实体检测器，使用Neo4j GDS库实现实体相似性分析和社区识别。
 **主要功能：**
 **建立实体投影图：**创建“实体的内存投影子图”，不是为了存储，而是为了“可控、高效、可计算地做推理与召回”。如果不做这一步，你的系统只能“查数据”，而做不了 **图级语义推理**。

 **使用KNN算法识别相似实体**：


 **社区感知搜索结合**：是Agent的设计哲学，表明了在搜索前，不急着进行搜索，先花点代价想想怎么进行搜索。

- **Community-aware Search → 降低探索空间**
- **Chain-of-Exploration → 发现隐性线索**
- **多级缓存 → 控制系统成本**
- **搜索策略回写 → 提升后续召回质量**



```
def enhance_search_with_coe(tool, query: str, keywords: Dict[str, List[str]]):
    """
    使用社区感知搜索结合 Chain-of-Exploration 结果对查询进行增强。
    该函数与旧版 `_enhance_search_with_coe` 逻辑一致，通过接收 `tool` 实例
    来复用其依赖对象，避免主类体积过大。
    """
    cache_key = f"coe_search:{query}"
    if hasattr(tool, "_coe_cache") and cache_key in tool._coe_cache:
        return tool._coe_cache[cache_key]
    community_context = tool.community_search.enhance_search(query, keywords)
    search_strategy = community_context.get("search_strategy", {})
    focus_entities = search_strategy.get("focus_entities", [])
    if not focus_entities:
        focus_entities = keywords.get("high_level", []) + keywords.get("low_level", [])
    if focus_entities:
        coe_cache_key = f"coe:{query}:{','.join(focus_entities[:3])}"
        if hasattr(tool, "_specific_coe_cache") and coe_cache_key in tool._specific_coe_cache:
            exploration_results = tool._specific_coe_cache[coe_cache_key]
        else:
            exploration_results = tool.chain_explorer.explore(
                query,
                focus_entities[:3],
                max_steps=3,
            )
            if not hasattr(tool, "_specific_coe_cache"):
                tool._specific_coe_cache = {}
            tool._specific_coe_cache[coe_cache_key] = exploration_results
        community_context["exploration_results"] = exploration_results
        discovered_entities = []
        for step in exploration_results.get("exploration_path", []):
            if step["step"] > 0:
                discovered_entities.append(step["node_id"])
        if discovered_entities:
            search_strategy["discovered_entities"] = discovered_entities
            community_context["search_strategy"] = search_strategy
    if not hasattr(tool, "_coe_cache"):
        tool._coe_cache = {}
    tool._coe_cache[cache_key] = community_context
    return community_context
```


**输入：**
```
query = "为什么企业级 Agent 系统需要 Router Agent？"
```

```
keywords = {
    "high_level": [
        "Agent 系统",
        "企业级架构"
    ],
    "low_level": [
        "Router Agent",
        "多智能体",
        "任务路由"
    ]
}
```

**输出：**
```
community_context = {
    "community": "Enterprise Multi-Agent Architecture",

    "search_strategy": {
        "focus_entities": [
            "Router Agent",
            "Multi-Agent Routing",
            "Task Decomposition"
        ],
        "discovered_entities": [
            "Intent Classification",
            "Skill Registry",
            "Failure Isolation"
        ],
        "intent": "architecture_reasoning"
    },

    "exploration_results": {
        "exploration_path": [
            {
                "step": 0,
                "node_id": "Router Agent",
                "reason": "用户问题直接提及"
            },
            {
                "step": 1,
                "node_id": "Intent Classification",
                "reason": "Router Agent 的核心能力之一"
            },
            {
                "step": 2,
                "node_id": "Skill Registry",
                "reason": "路由决策依赖可调用能力集合"
            },
            {
                "step": 3,
                "node_id": "Failure Isolation",
                "reason": "企业级系统引入 Router 的关键动机"
            }
        ]
    }
}
```



