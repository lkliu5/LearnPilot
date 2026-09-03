# TASK-004 Trusted-RAG-Canary

## 任务名称

Trusted RAG 生产灰度准入与 Canary 验证体系建设

## 背景

TASK-003 已完成 Trusted RAG 核心能力建设，包括：

-   Trusted RAG Service
-   Agent Tool 接入
-   Shadow 执行机制
-   Shadow Metrics 指标采集
-   Trusted RAG Gate 灰度准入策略

当前系统已经具备 Trusted RAG
离线运行能力，但由于缺少真实生产验证数据，Gate 当前结果为 NO-GO。

下一阶段不直接切换生产，而是在保持 Legacy
Agent、Workflow、API、前端稳定的前提下，完成 Trusted RAG
的生产灰度准备。

------------------------------------------------------------------------

# 目标

建立完整的 Trusted RAG Canary 发布闭环：

    真实请求
        |
    Shadow执行
        |
    指标采集
        |
    质量评估
        |
    Gate准入
        |
    Canary灰度
        |
    稳定观察
        |
    逐步扩大流量

------------------------------------------------------------------------

# 约束原则

## 不修改生产入口

本阶段：

-   不修改 Legacy Agent
-   不修改 Workflow
-   不修改 API Contract
-   不修改前端调用逻辑

Legacy 始终作为生产权威路径。

Trusted RAG 仅作为 Shadow / Canary 候选路径。

------------------------------------------------------------------------

# TASK-004-A Shadow Dataset Construction

## 目标

建立 Trusted RAG 真实评测样本集。

## 内容

新增：

    evaluation/
        trusted_rag_shadow_dataset.json

    docs/
        Trusted-RAG评测数据集说明.md

## 要求

至少：

-   100 条真实 Query
-   多类别覆盖
-   标准答案
-   人工质量标签

覆盖：

  类型            数量
  --------------- ------
  概念解释        20
  流程说明        20
  代码/技术问题   20
  多跳推理        20
  无答案拒答      20

------------------------------------------------------------------------

# TASK-004-B Legacy Baseline Benchmark

## 目标

建立 Legacy RAG 性能基线。

## 采集指标

性能：

-   P50 latency
-   P95 latency
-   P99 latency

稳定性：

-   timeout rate
-   error rate

质量：

-   answer correctness
-   evidence coverage

## 输出

    docs/Legacy-RAG性能基线报告.md

------------------------------------------------------------------------

# TASK-004-C Rerank Blind Evaluation

## 目标

验证 Rerank 是否真实提升检索质量。

## 数据格式

    query

    candidate documents

    human ranking

    rerank ranking

## 指标

-   Recall@K
-   MRR
-   NDCG@K
-   Human Preference

## 输出

    docs/Rerank盲测报告.md

------------------------------------------------------------------------

# TASK-004-D Fault Injection

## 目标

验证 Trusted RAG 故障情况下可以安全回退。

## 场景

### Retriever失败

验证：

    Trusted Retriever timeout

    ↓

    Legacy fallback

### VectorStore异常

验证：

    Vector DB unavailable

    ↓

    fallback

### Model异常

验证：

    LLM failure

    ↓

    controlled degradation

------------------------------------------------------------------------

# TASK-004-E Canary Release

## 发布策略

阶段：

    Stage 0:
    Shadow only

    Stage 1:
    5% Canary

    Stage 2:
    20% Canary

    Stage 3:
    50% Canary

    Stage 4:
    100%

------------------------------------------------------------------------

## Canary准入条件

必须满足：

### Quality

-   Trusted质量不低于Legacy
-   Evidence覆盖提升

### Latency

-   P95 不超过Legacy基线120%

### Reliability

-   error rate不高于Legacy

### Rerank

-   独立验证通过

------------------------------------------------------------------------

# 回滚策略

任何条件失败：

    Trusted RAG

    ↓

    BLOCK

    ↓

    Legacy

要求：

-   无用户感知中断
-   自动恢复Legacy路径
-   保存失败原因

------------------------------------------------------------------------

# 验收标准

## 数据

-   [ ] Shadow样本 \>=100
-   [ ] 人工标签完成

## 性能

-   [ ] Legacy P95完成采集
-   [ ] Trusted性能对比完成

## 质量

-   [ ] Rerank盲测完成
-   [ ] Evidence质量评估完成

## 稳定性

-   [ ] 超时测试完成
-   [ ] 故障注入完成
-   [ ] 自动回滚验证完成

------------------------------------------------------------------------

# 文件影响范围

## 预计新增

    backend/evaluation/
    docs/
    tests/

## 明确不修改

    frontend/
    Legacy Agent
    Workflow
    API接口
    用户交互页面

------------------------------------------------------------------------

# 最终目标

完成 Trusted RAG 从：

    Engineering Capability

到：

    Production Ready AI Infrastructure

的转变。
