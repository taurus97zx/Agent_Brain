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
