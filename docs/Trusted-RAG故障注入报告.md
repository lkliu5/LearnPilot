# Trusted RAG 故障注入报告

> 任务：TASK-004-D Trusted RAG 故障注入与回滚验证
>
> 机器可读结果：`backend/evaluation/trusted_rag_fault_results.json`
>
> 最终结论：**BLOCK**，Legacy 继续保持生产权威路径。

## 1. 验证边界

本次只新增离线 Fault Injection Harness，通过现有 `ResourceGenerationRAGShadowAdapter` 和可注入 Tool/Metric Sink 运行故障场景。没有修改 API、Workflow、Legacy Agent、Trusted RAG Service、已有 Gate 或生产路由。

所有场景均断言：

- Legacy 输出保持不变；
- Trusted 候选失败不覆盖 Legacy；
- 只保存结构化 reason 和异常类型，不保存异常消息；
- Shadow Event 不包含 query、Evidence、Legacy 正文或用户标识；
- 回滚建议固定为 `legacy`；
- Metrics Sink 异常不改变业务结果。

结果文件设置：

```text
evaluationType = offline_fault_injection
productionPerformance = false
productionMutation = false
legacyAuthority = true
```

## 2. 覆盖场景

| 场景 | 注入 | 结果 | 结构化原因 |
|---|---|---|---|
| Retriever 异常型超时 | 抛出 `TimeoutError` | PASS | `retriever.timeout_exception` |
| Retriever 普通异常 | 抛出 `RetrieverFailure` | PASS | `retriever.runtime_error` |
| Retriever 空 Evidence | 返回合法空 `RAGResponse` | PASS | `retriever.empty_evidence_canary_block` |
| Retriever 挂死探针 | 依赖超过截止时间且不抛异常 | **BLOCK** | `timeout.hard_hang_no_hard_deadline` |
| VectorStore collection 不可用 | `CollectionUnavailableError` | PASS | `vector_store.collection_unavailable` |
| VectorStore query 异常 | `VectorQueryError` | PASS | `vector_store.query_error` |
| VectorStore 数据异常 | `VectorDataError` | PASS | `vector_store.invalid_data` |
| Reranker 加载失败 | `RerankerLoadError` | PASS | `reranker.model_load_failure` |
| Reranker 推理失败 | `RerankerInferenceError` | PASS | `reranker.inference_hybrid_fallback_canary_block` |
| LLM 候选链异常 | `LLMDegradationError` | PASS | `llm.candidate_failure_legacy_fallback` |
| Metrics Sink 异常 | Sink `record()` 抛出异常 | PASS | `metrics.sink_failure_isolated` |

汇总为 `10 PASS / 1 BLOCK`。11 个场景的 `legacyPreserved=true`、`rollbackPath=legacy`、`contentSafe=true`。

## 3. Timeout 分类

### 3.1 异常型 timeout

Tool 立即抛出 `TimeoutError`：

- Shadow Adapter 返回 Legacy 权威结果；
- `shadow.error.error_type=TimeoutError`；
- Timeout/Error 可进入 Metrics；
- 结果中不保存异常消息；
- 实测约 1.0774 ms；
- 场景 PASS。

### 3.2 真实挂死型 timeout

为避免留下永久线程，测试使用 80 ms 的有界阻塞模拟“依赖不抛异常且不在截止时间内返回”，硬截止预算为 10 ms。

实测 Adapter 在约 81.7993 ms 后才返回。原因是当前实现使用 `ThreadPoolExecutor` 后等待两个 Future 完成，没有请求级硬 deadline、取消或独立进程隔离。虽然最终 Legacy 内容没有被覆盖，但主链路等待了 Trusted 依赖，不能满足“无用户感知中断”。

因此：

```text
timeoutKind = hard_hang
trustedIsolated = false
status = BLOCK
structuredReason = timeout.hard_hang_no_hard_deadline
```

本阶段按约束不修改生产代码解决该问题。未来必须另立任务设计底层客户端 timeout、并发隔离、取消/熔断和资源回收，再重新进行故障演练。

## 4. Empty Evidence

空 Evidence 不是 Python 异常，现有 Shadow Adapter 会产生 `shadow.result`。Fault Harness 额外执行 Canary fail-closed 判定：`evidence_count=0` 时阻断 Trusted 候选并保持 Legacy。

这验证了离线准入策略，但没有改变现有 Adapter 或生产路径。未来若真正进入 Canary，空 Evidence 的运行时路由规则仍需独立评审和实现。

## 5. VectorStore 故障

collection 不可用、query 异常和数据异常均在 Tool 边界被隔离：

- Legacy 结果不变；
- Event 只记录 `CollectionUnavailableError`、`VectorQueryError` 或 `VectorDataError`；
- 不保存底层连接串、query、数据正文或异常消息；
- 推荐路径固定为 Legacy。

这些是离线可控异常注入，不代表已经验证所有 Chroma 进程崩溃、文件锁、磁盘耗尽或数据文件损坏情形。

## 6. Model/Reranker/LLM 降级

### Reranker

- 加载失败：Trusted 候选被阻断并回到 Legacy；
- 推理失败：同时复用现有 `DecisionReranker` 验证 Hybrid 原顺序恢复，结果为 `reranker_error_hybrid_fallback`；随后 Canary 仍保持 Legacy 权威；
- 结构化结果标记 `componentFallback=hybrid_then_legacy`。

### LLM

Trusted RAG Service 本身不调用 LLM，因此本次只在隔离的候选生成边界注入 LLM 异常，验证受控降级到 Legacy。该结果不能解释为已经验证某个生产 LLM Provider 的网络超时或限流。

## 7. Metrics 故障

Metrics Sink 的 `record()` 抛出异常时：

- Tool 成功结果不变；
- Legacy 权威输出不变；
- Adapter 只记录 `traceId + errorType`；
- 不传播 Metrics 异常到业务；
- `metricsIsolated=true`，场景 PASS。

## 8. 最终结论

当前 `finalDecision=BLOCK`，唯一结构化阻断原因：

```text
timeout.hard_hang_no_hard_deadline
```

异常型超时、普通异常、空 Evidence、VectorStore、Reranker、LLM 候选边界和 Metrics 均验证了 Legacy 回退或隔离；但真实挂死型依赖仍会拖住 Adapter，因此不能批准 Canary。

## 9. 复现命令

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/evaluate_trusted_rag_faults.py `
  --output evaluation/trusted_rag_fault_results.json `
  --hard-timeout-budget-ms 10 `
  --hang-probe-ms 80
```

该命令只运行离线故障桩并写入 evaluation 结果，不连接或修改生产入口。
