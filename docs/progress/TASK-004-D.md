# TASK-004-D 完成总结

## 任务

`TASK-004-D Fault Injection`。

本阶段通过隔离离线 Harness 验证 Trusted RAG 候选路径故障时的 Legacy 回退、事件安全和 Metrics 隔离。没有修改生产代码解决发现的问题。

## 修改文件

- `backend/app/rag/canary_fault_injection.py`：11 类故障场景、结构化结果、Legacy 回退断言和 timeout 分类。
- `backend/scripts/evaluate_trusted_rag_faults.py`：离线故障注入 CLI 和环境记录。
- `backend/evaluation/trusted_rag_fault_results.json`：完整故障注入实测结果。
- `backend/tests/test_trusted_rag_fault_injection.py`：故障覆盖、内容安全、回滚、Metrics 隔离和 BLOCK 产物测试。
- `docs/Trusted-RAG故障注入报告.md`：场景、timeout 差异、能力缺口和最终结论。
- `docs/progress/TASK-004-D.md`：本阶段完成记录。

## 场景覆盖与结果

共 11 个场景：`10 PASS / 1 BLOCK`。

| 组件 | 场景 | 结果 |
|---|---|---|
| Retriever | `TimeoutError` | PASS |
| Retriever | 普通异常 | PASS |
| Retriever | 空 Evidence | PASS，Canary fail-closed |
| Retriever | 不抛异常的挂死探针 | **BLOCK** |
| VectorStore | collection 不可用 | PASS |
| VectorStore | query 异常 | PASS |
| VectorStore | 数据异常 | PASS |
| Reranker | 加载失败 | PASS |
| Reranker | 推理失败，Hybrid 原顺序恢复后保持 Legacy | PASS |
| LLM | 候选生成边界异常 | PASS |
| Metrics | Sink 异常 | PASS |

全部 11 个场景均满足：

- `legacyPreserved=true`；
- `rollbackPath=legacy`；
- `contentSafe=true`；
- 没有持久化 query、Evidence、Legacy 正文或异常消息。

## Timeout 结论

- 异常型 timeout：Tool 抛出 `TimeoutError`，约 1.0774 ms 返回 Legacy，结构化记录 `TimeoutError`，PASS。
- 挂死型 timeout：80 ms 有界阻塞超过 10 ms 硬截止预算，Adapter 约 81.7993 ms 后才返回；现有实现没有硬 deadline、取消或熔断，BLOCK。

最终结论：`BLOCK`。

唯一阻断原因：

```text
timeout.hard_hang_no_hard_deadline
```

本阶段按约束没有修改 `ResourceGenerationRAGShadowAdapter` 或其他生产代码。Legacy 继续保持生产权威路径。

## 故障注入命令

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/evaluate_trusted_rag_faults.py `
  --output evaluation/trusted_rag_fault_results.json `
  --hard-timeout-budget-ms 10 `
  --hang-probe-ms 80
```

实测：退出码 0，11 个场景全部完成，结果 JSON 成功写入。

## 测试命令与结果

定向回归：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q `
  tests/test_trusted_rag_fault_injection.py `
  tests/test_resource_rag_shadow.py `
  tests/test_agent_rag_shadow_metrics.py `
  tests/test_rerank_gate.py
```

实测：`20 passed in 1.62s`，0 failed、0 errors。

全量回归：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q --basetemp='.pytest_task004_d_full'
```

实测：`414 passed, 1 skipped, 1 warning in 104.58s`，0 failed、0 errors。warning 为既有 Starlette/httpx 弃用提示。

## 未修改范围

- 未修改 `frontend/`；
- 未修改 API 或 API Contract；
- 未修改 Legacy Agent；
- 未修改任何 Workflow；
- 未修改 Trusted RAG Service 主逻辑；
- 未修改现有 Shadow Adapter；
- 未修改已有 Gate；
- 未改变生产默认路径；
- 未接入或切换生产流量。

本阶段完成后停止，不开始 TASK-004-E。
