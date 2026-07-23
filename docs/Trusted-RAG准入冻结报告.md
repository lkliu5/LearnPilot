# Trusted RAG 准入冻结报告

> 任务：TASK-004-E4-B Trusted RAG 准入指标冻结与环境一致性验证
> 前置：TASK-004-E4-A（`671f8bf`）
> 日期：2026-07-23
> 边界：未开启 Canary，未修改生产入口、Agent Workflow 或切流权重。

## 1. 冻结结论

TrustedRAGGate v4 复跑结果为 **PASS**：Quality、Latency、Reliability、Rerank 四门均通过，
`block_reasons=[]`。当前状态定义为 **PASS_READY**，含义仅为“可提交人工 Canary 评审”；
不等于已批准或已启用 Canary。本任务保持 `canaryEnabled=false`、`productionMutation=false`。

机器证据：

- `backend/evaluation/trusted_rag_admission_freeze_e4b.json`
- `backend/evaluation/trusted_rag_gate_decision_e4b.json`

## 2. QualityGate v2

完整语义见《Trusted-RAG-QualityGate-v2指标定义》。冻结硬门如下：

| 指标 | 阈值 | 实测 | 结果 |
|---|---:|---:|---|
| relevance | ≥ 0.67 | 0.697143 | PASS |
| support_rate | ≥ 0.80 | 0.856000 | PASS |
| completeness | ≥ 0.30 | 0.314286 | PASS |
| source_coverage | ≥ 0.80 | 1.000000 | PASS |

Evidence overlap `0.303010` 与 confidence `0.999904` 进入 Gate snapshot diagnostic，均不再
单独决定答案质量。Overlap 从 v1 硬门移除是语义版本升级，不是把原 `0.70` 阈值下调。

## 3. Embedding Profile 决策

当前正式验证只承认以下单一 Profile：

| 字段 | 冻结值 |
|---|---|
| collection | `kb_chunks_trusted_validation_hash_d512_v1` |
| profile_id | `hash:deterministic_hash_v1:d512` |
| dimension | 512 |
| embedding_mode | `hash_fallback` |

源 `kb_chunks` 的 147 条文档被重新编码到独立验证 collection；源 collection 未删除、未覆盖。
新 collection metadata 完整声明 provider/model/dimension/profile_id，stored dimension 为 512，
评测脚本启用 `--require-declared-profile`，query profile 与 collection profile 不一致会直接终止。

本报告全部 Quality/Latency/Rerank 基线结果均属于 Hash Profile，**没有混入 Real BGE**。
因此 PASS_READY 只对该冻结 Profile 有效；Real BGE 若进入后续验证，必须新建 collection、
重新跑完整数据集并生成独立报告，不得与本结果拼接。

## 4. 目标环境 Latency

目标验证环境标识为 `competition-target-windows-cpu`：Windows 11、Python 3.12.13、CPU，
执行方式为 `local_target_validation_host`。125 条请求全部标记为 target-environment sample，
`performance_verified=true`。

| 指标 | 实测 |
|---|---:|
| 请求数 | 125 |
| P50 | 22.2397 ms |
| P95 | 24.1453 ms |
| timeout | 0 / 125（0%） |
| error | 0 / 125（0%） |
| fallback 触发 | 118 / 125 |
| fallback overhead mean | 0.160402 ms |
| fallback overhead P95 | 0.235700 ms |

P95 低于 1500 ms Gate 上限，Latency PASS。数据是单机 CPU 离线目标主机验证，不代表未来
并发流量容量；并发、资源争用和长窗口指标需在 E4-C Shadow 中继续观察。

## 5. RerankPolicy v1

E4-A 独立集上的 conditional 策略仍有 2 个退化 case，因此 v1 不宣称 Rerank 获益，直接
冻结为显式禁用。五类策略一致：

| query_type | enabled | fallback | reason |
|---|---|---|---|
| concept_explanation | false | hybrid | independent_validation_regression_policy_disabled |
| method_comparison | false | hybrid | independent_validation_regression_policy_disabled |
| operation_steps | false | hybrid | independent_validation_regression_policy_disabled |
| programming_practice | false | hybrid | independent_validation_regression_policy_disabled |
| comprehensive_question | false | hybrid | independent_validation_regression_policy_disabled |

125/125 请求保持 Hybrid 顺序，MRR/nDCG delta 均为 0，退化 case 数为 0。Gate 仅在
`policy_enabled=false`、`fallback=hybrid` 且退化数为 0 时允许 Rerank 子门 PASS；错误 fallback
会 fail-closed。该策略没有接入生产 Pipeline。

## 6. Gate 变化

| 子 Gate | E4-A | E4-B | 变化 |
|---|---|---|---|
| Quality | BLOCK | PASS | v2 四指标通过；overlap 改为 diagnostic |
| Latency | BLOCK | PASS | 125 条目标环境证据已验证 |
| Reliability | PASS | PASS | 0 timeout/error；11/11 故障场景通过 |
| Rerank | BLOCK | PASS | v1 全类型禁用，Hybrid fallback，退化 0 |
| Final | BLOCK | PASS_READY | 仅具备提交人工 Canary 评审资格 |

## 7. TASK-004-E4-C 建议

E4-C 应作为 Canary 评审与观测准备任务，仍需显式审批后才能切流：

1. 保持初始 Canary 权重为 0，评审通过后才设置最小非零权重，并验证自动回滚。
2. 针对操作步骤分层补充真实 Shadow 样本，单独观察 relevance/support；出现持续低于总体线即阻断。
3. 加入目标环境并发、资源争用、冷启动和长窗口 P95/P99；继续记录 timeout/error/fallback overhead。
4. RerankPolicy v1 维持全禁用。任何重新启用必须发布 v2，并用新的独立集证明退化 case=0。
5. 如切换 Real BGE，建立独立 Profile/collection 和全量准入证据，禁止复用或混合本 Hash 结果。
