# Agent-RAG Shadow 指标报告

> 任务：TASK-003-E4-B Agent-RAG Shadow 指标采集体系
>
> 前置：TASK-003-E3（`2c3aec2`）
>
> 结论：只采集和分析，不切换生产

## 1. 指标设计

### 1.1 Shadow Event

事件统一为 `shadow.request`、`shadow.result`、`shadow.error`，使用严格 Pydantic 模型并拒绝额外字段。

| 字段 | request | result | error | 说明 |
|---|---|---|---|---|
| `traceId` | 必填 | 必填 | 必填 | 链路关联标识 |
| `agent` | 必填 | 必填 | 必填 | Agent 名称 |
| `tool` | 必填 | 必填 | 必填 | Tool 名称 |
| `latency` | 空 | 必填 | 必填 | Tool 总耗时，毫秒 |
| `evidence_count` | 空 | 必填 | 空 | Evidence 数量 |
| `source_count` | 空 | 必填 | 空 | 去重来源数量 |
| `confidence` | 空 | 必填 | 空 | 检索启发式置信分数 |
| `error_type` | 空 | 空 | 必填 | 仅异常类型，不记录异常消息 |

事件和指标样本禁止出现 query 正文、用户信息、知识正文、Evidence 正文、Legacy 输出正文和异常消息。`extra="forbid"` 会拒绝携带这些额外字段的输入。

### 1.2 性能指标

- `total_latency`：从 Shadow Adapter 开始处理到 Legacy 与 Tool 两分支均结束的墙钟时间。
- `rag_latency`：优先读取 `serviceObservability.totalMs`，其次读取 RAG Pipeline `observability.totalMs`。
- `tool_latency`：Tool 工厂创建、请求适配和 RAG 调用的完整耗时。
- P50/P95：nearest-rank 口径，即升序样本的 `ceil(P × N)` 位。
- `timeout_rate`：根因异常类型包含 `timeout` 的样本数 / 总样本数。
- `error_rate`：存在 `error_type` 的样本数 / 总样本数。

### 1.3 质量指标

- `evidence_overlap`：Legacy 与 Trusted Evidence 引用集合的 Jaccard，相同引用为空集时记 1.0。
- `source_coverage`：Trusted RAG `TrustReport.coverage`。
- `confidence_distribution`：按 `[0, 0.5)`、`[0.5, 0.8)`、`[0.8, 1.0]` 三档计数。
- `reason_codes`：对成功样本的 RAG/TrustReport reason code 去重后计频。

Confidence 是检索启发式分数，不是答案正确概率；Evidence overlap 低可能表示补充了新来源，也可能表示检索偏移，必须结合人工抽样分析。

## 2. 采集方案

`ResourceGenerationRAGShadowAdapter` 保持 Legacy `AgentMessage` 为唯一权威结果。Legacy 与 Trusted RAG 由两个 worker 并发执行；RAG Tool 工厂移动到 Shadow worker 内创建，不继承请求线程或 Legacy 分支的 DB Session。测试使用两个真实 SQLAlchemy Session 验证实例身份和执行线程均隔离。

调用方可注入 `ShadowMetricsCollector`。每次结束生成一条无正文的 `ShadowMetricObservation`；收集器使用锁保护、默认最多保留 10,000 条，达到上限后按先进先出淘汰。`report()` 返回结构化性能和质量汇总。指标 Sink 异常只记录 `traceId + errorType`，不会改变 Legacy 结果或使主链失败。

当前采集器是进程内离线观测组件，不修改 Workflow、API 或生产调用链。后续若需跨进程持久化，应通过独立 Sink/队列消费同一无正文协议，不能向事件补充敏感正文。

## 3. 当前样例结果

确定性单元夹具包含 4 条样本：3 条成功、1 条 Timeout。该结果只验证统计口径，不代表生产性能。

| 指标 | 样例结果 |
|---|---:|
| sample / success | 4 / 3 |
| total latency P50 / P95 | 20 / 40 ms |
| RAG latency P50 | 15 ms |
| Tool latency P95 | 38 ms |
| timeout rate / error rate | 25% / 25% |
| Evidence overlap mean | 0.75 |
| Source coverage mean | 0.75 |
| Confidence low / medium / high | 1 / 1 / 1 |
| Reason codes | `grounded: 3`, `partial_coverage: 1` |

真实 Adapter 夹具同时验证：Trusted/Legacy 引用 Jaccard 为 `1/3`、Source coverage 为 `1.0`、Confidence 为 `0.91`、RAG latency 可从 Service metadata 提取为 `1.2 ms`，序列化指标中不含测试使用的敏感 query、用户标识或知识正文。

## 4. 接入门槛建议

以下仅是进入灰度评审的建议，不在本阶段执行生产切换：

1. 连续采集不少于 100 条真实 Shadow 样本，关键任务类型各不少于 20 条。
2. Tool error rate ≤ 2%，timeout rate ≤ 1%，P95 延迟满足演示和部署环境预算。
3. 平均 Source coverage ≥ 0.80；零引用重合样本占比需单独复核，Evidence overlap 不作为单一否决项。
4. Confidence 分布不能相对基线整体左移，低置信样本必须能通过 reason codes 定位原因。
5. Session 隔离、指标 Sink 故障和 Tool 故障均不得改变 Legacy 结果。
6. 达标只表示可进入小比例、可回滚灰度评审，不表示允许一次性替换 Legacy Agent。

当前没有生产 Shadow 样本，不能给出正式 GO 结论，继续保持只采集和分析。
