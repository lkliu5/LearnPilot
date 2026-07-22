# Legacy RAG 性能基线报告

> 任务：TASK-004-B Legacy/Trusted RAG 离线基准评估
>
> 数据集：`trusted-rag-shadow-representative-v1`
>
> 机器可读结果：`backend/evaluation/legacy_rag_baseline.json`
>
> 结论：这是本机、单进程、Hash Embedding 降级环境的离线基线，**不是生产性能**。

## 1. 评测边界

本次使用 TASK-004-A 的 100 条 representative evaluation cases，五类各 20 条。数据集明确设置 `productionShadowData=false`，不包含真实生产 Shadow 请求。

对照路径为：

- Legacy：`LegacyHybridRetriever`，即 TASK-003-C1 保存的旧 Hybrid 算法快照；
- Trusted：`TrustedRetrievalPipeline(HybridRetriever)`，只调用既有可信检索 Pipeline；
- 两者绑定同一个 `kb_chunks` Collection、同一个 Embedding 实例、相同 Top-K、相同超时预算和相同运行进程。

Benchmark 逐 case 交替 Legacy/Trusted 的先后顺序，避免固定由某一路承担全部预热成本。该脚本没有导入 API 或 Workflow，也没有修改生产默认 Retriever、Service 或路由。

## 2. 运行环境

| 项目 | 实测值 |
|---|---|
| dataset version | `trusted-rag-shadow-representative-v1` |
| dataset type | `representative_evaluation_dataset` |
| case count | 100 |
| collection | `kb_chunks` |
| collection chunks | 147 |
| requested embedding | `BAAI/bge-small-zh-v1.5`, 512 维 |
| actual embedding mode | `hash_fallback` |
| runtime | CPython 3.12.13, Windows 11 |
| Top-K | 5 |
| warm-up | 前 5 条，双路交替执行，不计入统计 |
| measured rounds | 1 |
| timeout budget | 5000 ms |

真实 BGE 加载失败，错误为本机 Torch `torch_python.dll` 权限拒绝，Embedder 按既有 Mock-first/降级策略使用 512 维确定性 Hash Embedding。报告完整保存了 `mode`、`profileId`、provider、model、dimension、fallback 状态和加载错误，没有将降级结果标记为真实 BGE。

## 3. 指标口径

### 3.1 性能与可靠性

- latency：单次同步检索的墙钟耗时；
- P50/P95/P99：nearest-rank；
- timeout：显式 `TimeoutError`，或调用完成耗时超过 5000 ms；
- error：Runner 抛出异常，仅保存异常类型，不保存异常正文；
- 本实现只观察超时，不声称可以硬取消永久阻塞的底层调用。

### 3.2 Evidence coverage

有答案样本按“已召回期望文档数 / 期望文档总数”计算；无答案样本只有在不返回 Evidence 时记为 1，否则记为 0。错误调用固定记为 0，避免通过排除失败样本抬高质量。

### 3.3 Correctness

当前 RAG Benchmark 比较的是检索输出，不生成最终答案。因此 `correctness` 是严格的 deterministic retrieval-support proxy：

1. 必须召回全部 `requiredDocumentIds`；
2. Evidence 正文必须覆盖全部 `requiredConcepts`；
3. 无答案样本必须返回空 Evidence；
4. 两项全部满足才记 1，否则记 0。

该指标不能解释为最终生成答案的人工正确率，也不能替代后续独立人工盲审。`standardAnswer` 用于冻结判定依据，而不是做字符串全等比较。

## 4. 总体结果

| 指标 | Legacy | Trusted | Trusted − Legacy |
|---|---:|---:|---:|
| mean latency | 16.1315 ms | 18.5136 ms | +2.3821 ms |
| P50 latency | 16.1170 ms | 18.5045 ms | +2.3875 ms |
| P95 latency | 17.7488 ms | 20.1622 ms | +2.4134 ms |
| P99 latency | 18.2812 ms | 20.6257 ms | +2.3445 ms |
| timeout rate | 0.0000 | 0.0000 | 0.0000 |
| error rate | 0.0000 | 0.0000 | 0.0000 |
| Evidence coverage | 0.171667 | 0.416667 | +0.245000 |
| Concept coverage | 0.112500 | 0.398333 | +0.285833 |
| Correctness proxy | 0.000000 | 0.220000 | +0.220000 |

Trusted/Legacy P95 比率为约 `1.1360`，在本次离线降级环境下低于 TASK-004 的 `1.20` 候选阈值。但该结论不能外推到真实 BGE、生产硬件或并发流量。

## 5. 分类结果

| 类别 | Legacy Evidence coverage | Trusted Evidence coverage | Legacy correctness | Trusted correctness |
|---|---:|---:|---:|---:|
| 概念解释 | 0.200000 | 0.600000 | 0.000000 | 0.100000 |
| 流程说明 | 0.141667 | 0.233333 | 0.000000 | 0.100000 |
| 代码/技术问题 | 0.300000 | 0.250000 | 0.000000 | 0.000000 |
| 多跳推理 | 0.216667 | 0.100000 | 0.000000 | 0.000000 |
| 无答案拒答 | 0.000000 | 0.900000 | 0.000000 | 0.900000 |

Trusted 的主要收益来自检索治理过滤了多数无答案结果，并改善概念解释召回；代码/技术和多跳推理的 Evidence coverage 没有优于 Legacy。严格 correctness proxy 对部分概念文字的精确覆盖敏感，不能据此评价最终回答的语言质量。

## 6. Gate 结论

**当前仍为 NO-GO，Legacy 保持生产权威路径。**

原因：

1. 数据集是 representative cases，不是真实生产 Shadow 请求；
2. 实际运行使用 Hash Embedding 降级，不是真实 BGE 性能；
3. 单机单进程、单轮、无并发，不能代表生产 P95/P99；
4. correctness 是检索支持代理，不是最终答案独立人工正确率；
5. 多跳推理和技术问题仍存在明显召回缺口；
6. TASK-004-C 独立 Rerank 盲测与 TASK-004-D 故障注入尚未完成。

本阶段没有修改已有 Gate，也没有把结果输入生产路由。即使某个离线阈值达标，也只形成后续评审证据，不产生流量切换。

## 7. 复现命令

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

未来真实 BGE 基准必须使用 `--embedding-mode real`。模型不可用时该模式应直接失败，禁止静默降级后继续声称为真实模型结果。
