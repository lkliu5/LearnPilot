# Agent-RAG Shadow 接入报告

> 任务：TASK-003-E3 Resource Agent Trusted RAG Shadow 接入
>
> 基线：`b05b87e`
>
> 结论：保持 Shadow，不进入正式接入

## 1. Shadow 架构

本阶段在现有 `ResourceGenerationAgentAdapter` 外新增 `ResourceGenerationRAGShadowAdapter`。它为同一任务创建两个并发分支：

```text
ResourceGenerationInput
  ├─ Legacy branch → ResourceGenerationAgentAdapter.run() → AgentMessage（权威结果）
  └─ Shadow branch → ToolRegistry → RAGTool.search() → RAGResponse（只观测）
                                      ↓
                     tool.request / tool.result / tool.error
                                      ↓
                   Evidence引用集合差异 + TrustReport + latency
```

Shadow 分支不向 Generator 注入 Trusted Evidence，不修改 Legacy `rag_context`，不参与质量路由，也不替换 Legacy 输出。RAGTool 失败时记录 `tool.error`，Legacy 结果仍可正常返回；Legacy 失败仍按原行为失败，不允许 Shadow 掩盖主链异常。

`ToolRegistry` 默认集中注册 `trusted_rag -> RAGTool`，支持后续以显式名称扩展其他 Tool。Agent 目录静态检查禁止直接导入 Retriever、VectorStore、Embedding、Reranker 或 Chroma，确保 Agent 只能经 Tool/Service 边界访问 RAG。

## 2. 调用链变化

现有 Workflow、API 与旧 Agent 调用链没有变化。新增的可选 Shadow 调用链为：

```text
Shadow调用方
  → ResourceGenerationRAGShadowAdapter.run()
    → [并发] Legacy Resource Agent
    → [并发] ToolRegistry.create_rag_tool()
               → RAGTool → RAGService → TrustedRetrievalPipeline
  ← Legacy AgentMessage + content-free Shadow events
```

结构化事件固定为：

- `tool.request`：traceId、taskId、agent、tool、timestamp。
- `tool.result`：增加 latency、evidence_count、TrustReport、result_difference。
- `tool.error`：增加 latency 和 error_type，不保存异常消息。

事件不保存 query、knowledge_scope 值、userId、Evidence 正文、Legacy 正文或 Tool 异常消息。

## 3. Legacy vs RAGTool 差异

工程验证夹具使用相同任务，Legacy 与 Trusted 各返回 2 条 Evidence 引用：

| 指标 | 结果 |
|---|---:|
| Legacy evidence count | 2 |
| Trusted evidence count | 2 |
| Count delta | 0 |
| Shared reference count | 1 |
| Legacy only | 1 |
| Trusted only | 1 |
| Reference Jaccard | 0.3333 |

该结果验证了差异计算和“数量相同不等于来源一致”的可观测能力，不代表真实语料质量结论。Legacy AgentMessage 在成功和 Tool 失败场景均保持权威，测试确认 Shadow 不改变生成结果。

## 4. 延迟分析

两条分支由两个 worker 并发执行；线程屏障测试证明 Legacy 与 Tool 分支会同时进入执行段。因此 Shadow 总等待时间原则上接近较慢分支，而不是两条分支耗时相加。

每次结果分别记录 `legacy_latency_ms` 与 `tool_latency_ms`，`tool.result` / `tool.error` 同步记录 Tool latency。当前定向测试为内存夹具，`11 passed in 0.82s`，不能外推真实模型、Chroma、SQLite 会话或生产并发下的 P50/P95。正式接入评审前必须采集真实 Shadow 流量并设置超时、线程池/队列上限和熔断。

## 5. Evidence 质量分析

工程夹具的 Trusted TrustReport 为：retrieval confidence `0.91`、evidence count `2`、source count `2`、coverage `1.0`。Shadow 事件完整保留 TrustReport，同时仅用文档/切片引用计算集合重合度，不读取或持久化知识正文。

当前可以判断：

- Evidence 数量、来源覆盖和 Legacy/Trusted 引用差异已可追踪。
- Tool 失败不会污染主链结果，降级边界有效。
- 尚无真实任务样本，无法判断 Trusted Evidence 是否提升生成接地率、Citation Precision/Recall 或最终质量评分。
- retrieval confidence 是启发式检索分数，不应解释为答案正确概率。

## 6. 是否进入正式接入

结论：**暂不进入正式接入，继续 Shadow。**

原因：当前只完成协议、并发隔离、事件安全和工程夹具验证；没有真实 Shadow 样本量、生产延迟分位数、Tool 错误率、Evidence 人工盲评、生成质量对照和 DB/线程安全压测。正式切换前至少需要：

1. 独立真实任务集与连续 Shadow 流量验证。
2. Evidence 相关性、来源完整性、引用准确率和生成接地率对比。
3. P50/P95/P99、超时率、队列等待和错误率门槛。
4. Tool 超时、熔断、取消与资源隔离故障注入。
5. 先进行小比例可回滚灰度，再决定是否以 Trusted Evidence 替代 Legacy `rag_context`。
