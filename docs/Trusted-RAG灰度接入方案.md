# Trusted RAG 灰度接入方案

> 任务：TASK-003-E4-C Trusted RAG 灰度准入策略设计
>
> 前置：TASK-003-E4-B（`331dd24`）
>
> 范围：只设计和离线验证；不修改生产入口、Legacy Agent、Workflow 或 API。

## 1. Gate 设计

`TrustedRAGGate` 是只读、fail-closed 的 Migration Gate 协议。离线评估器读取历史
`ShadowMetricObservation`、同环境 Legacy P95 基线和独立 Rerank 评估，输出：

- `quality_pass`：Evidence overlap、Source coverage、Confidence 三项均达标且没有缺失样本；
- `latency_pass`：Trusted Tool P95 / Legacy P95 不超过配置上限；
- `reliability_pass`：样本量、Timeout rate、Error rate 均达标；
- `rerank_pass`：独立验证集上 MRR、nDCG@3、nDCG@5 无总体回归且无退化案例；
- `final_decision`：四项全通过才为 `pass`，否则为 `block`；
- `pass_count`、`block_count`、`block_reasons`：供离线评审审计；
- `recommended_path`：通过时仅表示可申请 `trusted_rag_canary`，阻断时固定为 `legacy`。

缺失关键数据与数据不足均不允许推断为通过。该协议不连接路由，不会直接造成流量切换。

默认阈值如下，部署环境可通过 `TrustedRAGGateConfig` 显式覆盖并版本化：

| Gate | 指标 | 默认阈值 | 方向 |
|---|---|---:|---|
| Quality | Evidence overlap mean | 0.70 | `>=` |
| Quality | Source coverage mean | 0.80 | `>=` |
| Quality | Confidence mean | 0.80 | `>=` |
| Latency | Trusted/Legacy P95 ratio | 1.50 | `<=` |
| Reliability | Timeout rate | 1% | `<=` |
| Reliability | Error rate | 2% | `<=` |
| Reliability | Shadow sample count | 100 | `>=` |

Evidence overlap 只表示引用集合 Jaccard，Confidence 只表示检索相对强度，二者都不等于答案正确率。阈值只能用于准入评审，必须继续配合人工盲审和失败案例分析。

## 2. 指标体系

### 2.1 质量

只统计 `error_type is None` 的成功样本。三项取成功样本算术均值；任一成功样本缺失对应字段时，质量门立即阻断，原因分别为
`quality.evidence_overlap_missing`、`quality.source_coverage_missing`、`quality.confidence_missing`。

### 2.2 性能

Trusted P95 使用历史 Shadow 的 `tool_latency`，沿用 nearest-rank 口径；分母必须是同部署环境、同任务分布和同时间窗的 Legacy P95。未提供或分母无效时以 `latency.p95_latency_ratio_missing` 阻断，禁止跨环境拼接基线。

### 2.3 可靠性

`timeout_rate = timed_out 样本数 / 总样本数`，`error_rate = error_type 非空样本数 / 总样本数`。无样本时两项均视为缺失；少于 100 条时增加 `reliability.sample_count_below_minimum`。真实验收还应满足关键任务类型各不少于 20 条。

### 2.4 Rerank

Rerank 不是仅凭 D3-C 同一 40 条探索集上的收益即可放行。必须提交独立、冻结、盲标验证集的 `RerankAssessment`：

1. `independent_validation=true`；
2. MRR、nDCG@3、nDCG@5 delta 均不为负；
3. `degraded_case_count=0`。

任一条件不满足即阻断。生产硬件延迟、超时、并发、熔断仍需在灰度前单独压测。

## 3. 灰度流程

本阶段只完成步骤 1，不授权执行后续流量切换：

1. **Shadow 采集**：Legacy 继续提供唯一权威结果；Trusted RAG 只采集无正文指标。
2. **离线冻结**：冻结时间窗、任务分层、Gate 配置、Legacy 基线与独立 Rerank 结果。
3. **准入评审**：运行 Gate；四门全通过并完成敏感信息、故障注入和人工盲审后，才可提出灰度变更。
4. **小流量灰度**：建议按 1% → 5% → 20% → 50% 分级，每级设置观察窗，不自动晋级。
5. **全量评审**：灰度全程无门槛突破、回滚演练成功后，另立任务评审是否扩大；Legacy 在稳定期内保留。

任何灰度实现都必须另行修改生产路由并走独立评审，本任务没有进行此类修改。

## 4. 回滚机制

当前离线协议采用确定性回滚建议：四个子门中任一失败，`final_decision=block` 且
`recommended_path=legacy`。这保证本阶段所有失败结论都保持 Legacy，不会误建议 Trusted RAG 灰度。

未来灰度任务应实现并验证以下运行时机制，但不属于本次改动：

- Legacy 路径始终可用，灰度只做可撤销的路由选择；
- Trusted RAG 超时、异常、无有效 Evidence、熔断或指标越界时，请求级回退 Legacy；
- 窗口内 Timeout/Error/P95 或质量指标越界时，自动将灰度比例归零；
- 回滚不依赖 Trusted RAG 自身组件，记录 traceId、原因码、配置版本和发生时间；
- 回滚后重新进入 Shadow，只有新时间窗重新通过 Gate 才能再次申请灰度。

## 5. 当前是否满足灰度条件

**结论：不满足，当前为 NO-GO，继续保持 Legacy。**

按已提交证据进行离线评估：

| 子门 | 结果 | 原因 |
|---|---|---|
| Quality | BLOCK | 尚无持久化真实 Shadow 样本，三项质量指标缺失 |
| Latency | BLOCK | 尚无同环境 Legacy P95 基线，无法计算 P95 ratio |
| Reliability | BLOCK | 真实样本为 0，低于 100，Timeout/Error rate 缺失 |
| Rerank | BLOCK | D3-C 40 条结果与策略选择共用数据，未完成独立验证 |

离线汇总为 **0 PASS / 4 BLOCK**。E4-B 的 4 条确定性夹具仅验证统计口径，不代表真实流量，不能计入正式准入样本。D3-C conditional 的探索结果虽为 MRR `+0.035715`、nDCG@3 `+0.032129`、nDCG@5 `+0.019824` 且当前夹具无退化案例，但仍存在同集选择与评估的过拟合风险。

进入下一次灰度评审前至少需要：采集不少于 100 条分层真实 Shadow 样本；取得同环境 Legacy P95；建立独立盲标 Rerank 验证集；完成生产硬件压测和回滚故障注入。完成这些前置只代表可重新运行 Gate，不代表自动批准上线。

## 6. 离线验证

实现位于 `backend/app/agents/trusted_rag_gate.py`，测试位于
`backend/tests/test_trusted_rag_gate.py`。覆盖 Gate 全通过、可配置阈值阻断、指标缺失 fail-closed，以及任一 Trusted RAG 子门失败时保持 Legacy 推荐路径。
