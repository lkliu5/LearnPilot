# Trusted RAG 准入条件补齐报告

> 任务：TASK-004-E2 Trusted RAG 准入条件补齐与可靠性增强
>
> 前置：TASK-004-E1（`8ac58dc`）
>
> 边界：只增强离线 Shadow/Gate/故障注入；未修改生产入口、Agent 业务逻辑或 Workflow。

## 1. BLOCK 原因

E1 的直接可靠性阻断原因是 `timeout.hard_hang_no_hard_deadline`：不抛异常的 Trusted Shadow 依赖会使原 Adapter 等待 worker 完成。故障注入结果为 `10 PASS / 1 BLOCK`，失败率 `9.0909%`。

此外，正式 Gate 仍缺少两类不能由代码伪造的准入证据：

- 未提供目标环境、冻结窗口内不少于 100 条的真实 Shadow 数据，质量均值、P95、Timeout/Error rate 均缺失；
- D3-C 独立盲测仍为 provisional，人工偏好与相关性复核未完成，且有 2 个 `recall@3` 退化案例。

## 2. 修复方案

### 2.1 Hard Deadline 与隔离

新增离线 `ShadowDeadlineExecutor`：

- 每个 Shadow task 必须传入正的 `deadline_ms`；
- deadline 到期后设置协作式 cancellation event，并立即返回 `shadow.deadline_exceeded`；
- worker 为 daemon 隔离线程，不参与 Legacy 权威结果；挂死 worker 不阻塞调用方或进程退出；
- 使用有界 semaphore 限制未退出 worker 数，舱位耗尽 fail-closed 为 `shadow.isolation_capacity_exhausted`；
- Python 无法安全强杀阻塞线程，因此底层依赖仍应配置原生 timeout；本实现用“取消信号 + 隔离 + 有界容量”控制不可取消依赖。

该执行器当前只接入离线故障注入，不修改现有生产入口。

### 2.2 ShadowEvaluationDataset 协议

新增 `trusted-rag-shadow-evaluation-v1` 严格协议。逐请求只允许：

- `request_id`、`query_type`；
- `latency`：total/rag/tool 毫秒指标；
- `quality_metrics`：Evidence overlap、Source coverage、Confidence；
- `reliability_metrics`：Timeout、错误类型、timeout reason、取消/隔离状态、Legacy 保持状态。

模型使用 `extra="forbid"`，因此 query 正文、用户信息、知识/Evidence 正文等字段会被拒绝。`request_id` 必须唯一；数据集可聚合 P95、质量均值、Timeout/Error rate 和 query type 分层计数。

### 2.3 Gate 增强

`TrustedRAGGate` 现在同时支持旧 `ShadowMetrics` 聚合输入和完整 `ShadowEvaluationDataset`。完整数据集模式额外检查：

- 五类 query type 各不少于 20 条；
- 所有 timeout 均已隔离；
- 所有样本均保持 Legacy；
- 目标环境性能已验证。

输出新增 `remediation`，并在 snapshot 中记录输入类型和 query type 计数。任何缺失或不达标仍 fail-closed。

## 3. 修复结果

重新执行 10 ms deadline、80 ms 挂死探针：

| 项目 | E1 | E2 |
|---|---:|---:|
| 故障场景 | 11 | 11 |
| PASS / BLOCK | 10 / 1 | 11 / 0 |
| Fault failure rate | 9.0909% | 0% |
| Hard hang | 未隔离 | deadline 到期、取消已请求、worker 已隔离 |
| Legacy | 保持 | 保持 |

机器结果：`backend/evaluation/trusted_rag_fault_results.json`，schema 已升级为 `trusted-rag-fault-injection-v2`。

## 4. D3-C Rerank 退化分析

两例均属于概念/比较解释型 query，退化机制相同：高相关候选由第 3 位升到第 1 位，提升 nDCG；但 Baseline 第 1 位的次相关 Evidence 被移出 Top-3，导致 `recall@3` 从 1.0 降为 0.5。

| Case | Query type | 排名变化 | Evidence 变化 |
|---|---|---|---|
| `t004c_blind_11` | 因果概念解释 | 高相关 `T8X3`：3→1；次相关 `A7K2`：1→5 | Top-3 丢失次相关 Evidence，`recall@3 -0.5`；nDCG@3 `+0.327614` |
| `t004c_blind_20` | 对比概念解释 | 高相关 `T8X3`：3→1；次相关 `A7K2`：1→4 | Top-3 丢失次相关 Evidence，`recall@3 -0.5`；nDCG@3 `+0.327614` |

结论：当前 20 例中仅 2 例且都在宽泛的概念解释类，证据不足以直接禁用整个 query type，**暂不建议粗粒度类型门控**。进入 Canary 前**需要 fallback**：当 rerank 会把 Baseline Top-3 的高置信 Evidence 移出 Top-3 时，采用受约束重排/Hybrid 原序回退，并重新冻结盲测；人工复核仍是解除 Rerank Gate 的必要条件。

## 5. Gate 重新评估

机器结果：`backend/evaluation/trusted_rag_gate_decision.json`，schema 已升级为 `trusted-rag-canary-gate-v2`。

- Hard hang、fault failure rate、trusted not isolated 三个阻断原因已消失；
- 故障注入子证据由 BLOCK 变为 PASS，failure rate 为 0；
- 正式最终结果仍为 `BLOCK`：缺真实 Shadow 冻结数据，且 Rerank 人工复核/退化处置未完成；
- remediation 已明确为补采 Shadow 质量与性能数据、验证目标环境延迟、补齐可靠性指标、应用 Rerank fallback 并重新验证。

因此，系统已具备开展 Canary **准入评估**所需的 deadline、数据协议和 Gate 能力，但**尚不具备开启 Canary 流量的证据条件**。继续保持 Legacy，生产 Canary 权重为零。

## 6. 验证结果

```text
聚焦测试：19 passed in 1.93s
全量测试：427 passed, 1 skipped, 1 warning in 98.92s
```

全量命令使用工作区临时目录规避系统 `%TEMP%` 权限问题：

```powershell
cd backend
python -m pytest -q --basetemp .pytest_task004_e2_full
```

warning 为既有 Starlette/httpx 弃用提示，无测试错误。

## 7. TASK-004-E3 建议

1. 在目标部署环境冻结 100+ 条真实无正文 ShadowEvaluationDataset，五类各 20+，完成质量、P95、Timeout/Error rate 采集。
2. 为底层 Retriever/VectorStore/Reranker 客户端补原生 timeout，并做隔离舱位耗尽与熔断恢复演练。
3. 完成 D3-C 独立人工相关性/偏好复核，实现“Top-3 Evidence 保护 + Hybrid fallback”的离线策略后重跑盲测。
4. 仅当四个子 Gate 均 PASS 时，提交独立的最小流量 Canary 变更评审；E3 仍不应由离线脚本直接切流。
