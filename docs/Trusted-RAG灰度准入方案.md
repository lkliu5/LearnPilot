# Trusted RAG 灰度准入方案

> 任务：TASK-004-E1 Trusted RAG 灰度准入 Gate
>
> 前置：TASK-004-D（`ca82417`）
>
> 边界：只实现 Gate 与离线评估；不修改 API、Agent、Workflow 或生产 RAG 入口。

## 1. Gate 设计

`TrustedRAGGate` 是纯函数式、fail-closed 的离线准入判断器。输入为聚合后的 `ShadowMetrics` 和 `FaultInjectionResults`，输出 `CanaryDecision`。它不持有路由能力，不会修改灰度比例或调用生产 RAG。

输出字段：

- `quality_pass`：Shadow 质量指标全部存在并达标；
- `latency_pass`：P95 存在、来源已验证且没有超过阈值；
- `reliability_pass`：样本量、Timeout/Error rate、故障注入失败率及隔离/回滚约束全部达标；
- `rerank_pass`：独立盲测、人工复核、非临时指标、聚合收益与退化案例全部达标；
- `final_decision`：四个子门全部通过才为 `PASS`，否则为 `BLOCK`；
- `block_reasons`：稳定、可审计的结构化原因码；
- `rollback_recommended`、`recommended_action`：阻断时建议保持 Legacy 并将 Canary 权重置零。该字段只是离线建议，本任务不会执行回滚。

## 2. 阈值与判定

默认阈值由 `TrustedRAGGateConfig` 版本化管理：

| 子门 | 指标 | 默认准入阈值 |
|---|---|---:|
| Quality | Evidence overlap mean | `>= 0.70` |
| Quality | Source coverage mean | `>= 0.80` |
| Quality | Confidence mean | `>= 0.80` |
| Latency | Shadow P95 | `<= 1500 ms` |
| Reliability | Shadow sample count | `>= 100` |
| Reliability | Timeout rate | `<= 1%` |
| Reliability | Error rate | `<= 2%` |
| Reliability | Fault failure rate | `<= 0%` |
| Rerank | MRR、nDCG@3、nDCG@5 delta | 均 `>= 0` |
| Rerank | degraded case count | `<= 0` |

P95 必须来自目标部署环境的已验证 Shadow 性能数据。离线夹具或 `productionPerformance=false` 的实验数据不能冒充生产性能，因此还要求 `performance_verified=true`。

故障失败率计算为 `block_count / scenario_count`。除此之外，每个故障场景必须同时满足：`status=PASS`、`legacyPreserved=true`、`trustedIsolated=true`、`rollbackPath=legacy`、`contentSafe=true`。汇总率与场景级约束任一失败均阻断 Reliability。

Rerank 除聚合指标非负外，还要求：

1. 使用独立验证集；
2. 指标不再标记为 provisional；
3. 人工偏好与相关性复核均完成；
4. 不存在退化案例。

《Rerank 融合策略优化报告》的 40 条探索实验不能单独满足以上条件，Confidence 也只代表检索启发式强度，不解释为答案正确概率。

## 3. 缺失与失败处理

Gate 不对缺失数据做零值填充或乐观推断：

- Shadow 质量、P95、Timeout/Error rate 或样本量缺失：对应子门阻断；
- Fault Injection Results 缺失或场景为空：Reliability 阻断；
- 故障失败率超过 0：Reliability 阻断并展开场景级原因；
- Rerank 结果缺失、仍为 provisional、人工复核未完成或存在退化：Rerank 阻断；
- 任一子门阻断：`final_decision=BLOCK`、`rollback_recommended=true`、`recommended_action=keep_legacy_and_set_canary_weight_to_zero`。

`recommended_action` 是未来 Canary 控制面的建议契约，不会由当前离线评估器自动执行，因而没有修改生产入口。

## 4. 当前准入结果

机器可读结果：`backend/evaluation/trusted_rag_gate_decision.json`。

**当前结论：BLOCK，不允许进入 Canary，继续保持 Legacy。**

| 子门 | 结果 | 当前证据 |
|---|---|---|
| Quality | BLOCK | 没有可用于正式准入的真实 Shadow 聚合质量指标 |
| Latency | BLOCK | 没有目标环境中已验证的完整 Shadow P95；Rerank CPU 离线耗时不等于生产链路 P95 |
| Reliability | BLOCK | Shadow 样本量、Timeout/Error rate 缺失；故障注入为 `10 PASS / 1 BLOCK`，失败率 `9.0909%` |
| Rerank | BLOCK | 独立盲测仍为 provisional，人工复核未完成，存在 2 个退化案例 |

故障注入的直接阻断项为 `timeout.hard_hang_no_hard_deadline`，且该场景 `trustedIsolated=false`。这说明异常型 Timeout 虽能回退，但不抛异常的挂死依赖仍可能拖住调用链。

当前输出为四门全部 BLOCK，并给出自动回滚建议：保持 Legacy、Canary 权重为零。该建议与《Trusted RAG 故障注入报告》的结论一致。

## 5. 离线评估与复现

实现文件：

- `backend/app/rag/trusted_rag_gate.py`
- `backend/scripts/evaluate_trusted_rag_gate.py`
- `backend/tests/test_trusted_rag_canary_gate.py`

复现当前决策：

```powershell
cd backend
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/evaluate_trusted_rag_gate.py
```

提供真实 Shadow 聚合指标时，可增加 `--shadow-metrics <json>`。输入模型拒绝额外字段，指标文件不得包含 query、Evidence、Legacy 正文或用户信息。

测试覆盖：全通过 Gate、单指标失败、多指标失败、数据缺失、自动回滚建议，以及 TASK-004 盲测结果为 provisional 时阻断。

## 6. TASK-004-E2 建议

E2 建议只做“可撤销 Canary 控制面设计与演练”，仍先不扩大流量：

1. 修复并验证请求级硬 deadline、取消、并发隔离与熔断，重新运行 D 的挂死型故障注入；
2. 冻结不少于 100 条真实、分层 Shadow 样本，补齐质量、P95、Timeout/Error rate，并记录环境与窗口版本；
3. 完成独立 Rerank 人工复核，处理 2 个退化案例后重新冻结评估；
4. 设计独立于 Trusted RAG 的 Canary 权重开关与自动回滚状态机，使用 Gate 输出做演练输入，但生产接入另立评审；
5. 只有 E1 Gate 重新得到 `PASS` 后，才允许提交最小流量 Canary 变更申请，不能由离线脚本直接切流。
