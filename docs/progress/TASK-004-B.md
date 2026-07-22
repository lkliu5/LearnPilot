# TASK-004-B 完成总结

## 任务

`TASK-004-B Legacy Baseline Benchmark`。

本阶段使用 TASK-004-A 的 100 条 representative evaluation cases，在同一离线环境中比较 Legacy RAG 与 Trusted RAG。没有接入生产请求或修改生产默认路径。

## 修改文件

- `backend/app/rag/canary_benchmark.py`：双路交替执行、P50/P95/P99、可靠性和检索质量代理指标。
- `backend/scripts/benchmark_rag_canary.py`：离线 CLI、统一 Embedding/Collection、环境记录和 JSON 输出。
- `backend/evaluation/legacy_rag_baseline.json`：100 条样本的本机完整 Benchmark 结果。
- `backend/tests/test_canary_benchmark.py`：数据来源、指标、异常脱敏、输入边界和基线产物契约测试。
- `docs/Legacy-RAG性能基线报告.md`：指标口径、环境、总体/分类结果、限制和 NO-GO 结论。
- `docs/progress/TASK-004-B.md`：本阶段完成记录。

## Benchmark 环境

- dataset：`trusted-rag-shadow-representative-v1`，100 条，非生产 Shadow 数据；
- collection：`kb_chunks`，147 个 chunk；
- runtime：CPython 3.12.13 / Windows 11；
- Top-K：5；warm-up：5 条；measured rounds：1；timeout：5000 ms；
- requested embedding：`BAAI/bge-small-zh-v1.5`，512 维；
- actual embedding：`hash_fallback`；
- 降级原因：本机 Torch `torch_python.dll` 权限拒绝。

结果明确设置 `productionPerformance=false`，不能描述为真实 BGE 或生产性能。

## Benchmark 实测摘要

| 指标 | Legacy | Trusted | Trusted − Legacy |
|---|---:|---:|---:|
| P50 latency | 16.1170 ms | 18.5045 ms | +2.3875 ms |
| P95 latency | 17.7488 ms | 20.1622 ms | +2.4134 ms |
| P99 latency | 18.2812 ms | 20.6257 ms | +2.3445 ms |
| timeout rate | 0.0000 | 0.0000 | 0.0000 |
| error rate | 0.0000 | 0.0000 | 0.0000 |
| Evidence coverage | 0.171667 | 0.416667 | +0.245000 |
| Correctness proxy | 0.000000 | 0.220000 | +0.220000 |

P95 比率约为 `1.1360`。Correctness 是“全部期望文档与必需概念均被 Evidence 支持”的严格检索代理，不是最终生成答案的人工正确率。

当前结论仍为 NO-GO：数据不是生产请求、Embedding 已降级、没有并发/多轮生产硬件压测，且 TASK-004-C/D 尚未完成。Legacy 继续保持生产权威路径。

## Benchmark 命令

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/benchmark_rag_canary.py `
  --output evaluation/legacy_rag_baseline.json `
  --collection kb_chunks `
  --embedding-mode configured `
  --top-k 5 `
  --rounds 1 `
  --warmup-cases 5 `
  --timeout-ms 5000
```

实测：进程退出码 0，Legacy/Trusted 各完成 100/100 条，JSON 成功写入。

## 测试命令与实测结果

定向测试：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q tests/test_canary_benchmark.py tests/test_trusted_rag_shadow_dataset.py
```

实测：`10 passed in 2.54s`，0 failed、0 errors。

全量回归：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -q --basetemp='.pytest_task004_b_full'
```

实测：`403 passed, 1 skipped, 1 warning in 102.40s`，0 failed、0 errors。warning 为既有 Starlette/httpx 弃用提示。

## 未修改范围

- 未修改 `frontend/`；
- 未修改 API 或 API Contract；
- 未修改 Legacy Agent；
- 未修改任何 Workflow；
- 未修改 Trusted RAG Service 主逻辑；
- 未修改已有 Gate；
- 未改变生产默认路径；
- 未接入或切换生产流量。

本阶段完成后停止，不开始 TASK-004-C。
