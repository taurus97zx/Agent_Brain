#### 问题一：在RAG知识库构建中，我们需要存储联通过去5年的客服工单记录（含用户长文本投诉内容），数据量是PB级的。请问在Hive中，你如何设计表结构来存储这些长文本？特别是考虑到后续PySpark读取这些数据去做向量化（Embedding）时，如何设计分区策略以避免小文件过多或读取倾斜？

客服投诉内容按照String类型来定义，按照天进行分区，存储格式采用ORC列式存储，提升压缩率和扫描效率，为防止小文件问题，在时间分区下对ticket_id做Hash分桶，每个分区控制在128～512个bucket，保证单文件大小在1GB左右。





#### 问题二：在Hive中，如果你直接对几亿条数据使用 Order By，会有什么后果？**Sort By、Distribute By 和 Cluster By 有什么区别？** 在联通这个场景下，你会如何组合使用它们来既保证有序又不撑爆集群？


在Hive中，ORDER BY 是全局排序，会强制所有数据进入一个Reducer。如果对几亿甚至PB级数据使用 ORDER BY，会导致单节点排序瓶颈，严重时会出现内存溢出或任务失败。

**错误写法：**
```
INSERT OVERWRITE TABLE dwd_ticket
SELECT *
FROM ods_ticket
ORDER BY create_time;
```

**正确写法：**
```
SET mapreduce.job.reduces=256;

INSERT OVERWRITE TABLE dwd_ticket
PARTITION (dt)
SELECT
    ticket_id,
    user_id,
    complaint_text,
    create_time,
    dt
FROM ods_ticket
DISTRIBUTE BY dt, hash(ticket_id)
SORT BY dt, create_time;
```

**执行步骤：**
```
dt=2026-02-01 → Reducer1
dt=2026-02-02 → Reducer2
dt=2026-02-03 → Reducer3
```



##### 问题三： 当后端规则库更新时，**你如何保证向量数据库的‘读写一致性’？** 你在索引重建期间是如何做‘平滑过渡’的，以防用户在 12:00 重建索引时查到 11:59 的过期资费？

我们在资费这类强一致性场景中，采用“主库权威 + 双索引版本 + 原子切换 + 增量同步”的方案来保证读写一致性。
第一，向量库只负责语义召回，不直接作为资费的最终数据源。在生成答案前，我们会根据召回到的套餐实体，实时查询业务主库做二次校验，确保价格始终来自最新规则。
第二，在索引重建时，我们采用双版本索引策略。例如线上使用 index_v1 服务，同时后台构建 index_v2。构建完成后，通过 alias 做原子切换，整个过程对用户无感知，也不会出现半新半旧的数据。
第三，日常资费变更采用 CDC 增量索引机制，只更新受影响的文档，通常可以在几十秒内同步到向量库，避免整库重建带来的不一致窗口。

因此，即使在12:00资费更新、12:00–12:02索引重建期间，系统仍然通过“旧索引召回 + 主库实时校验”的方式保证用户查到的是最新资费，实现平滑过渡。
