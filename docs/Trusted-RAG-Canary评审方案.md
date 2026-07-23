# Trusted RAG Canary 评审方案

> 任务：TASK-004-E4-C Trusted RAG Canary 评审与灰度策略设计
>
> 前置：TASK-004-E4-B（`c6f767a`）
>
> 日期：2026-07-23
>
> 边界：仅设计离线评审协议和纯状态机；不修改 API、Agent、Workflow、生产入口或生产权重。

## 1. 当前 PASS_READY 依据

E4-B 的 `TrustedRAGGate v4` 冻结结果为四门 PASS、`block_reasons=[]`，因而状态解释为
**PASS_READY**。它只表示具备提交人工 Canary 评审的资格，不表示已经批准切流。

| Gate | 冻结证据 | 结论 |
|---|---|---|
| QualityGate v2 | relevance `0.697143`、support `0.856000`、completeness `0.314286`、source coverage `1.000000` | PASS |
| Latency | 目标 Windows CPU 环境 125 请求，P95 `24.1453 ms`，上限 `1500 ms` | PASS |
| Reliability | timeout/error 均 `0%`；11/11 故障场景通过 | PASS |
| RerankPolicy v1 | 全类型显式禁用，Hybrid fallback，退化 case 为 0 | PASS |

该资格仅适用于冻结的 Hash Profile
`hash:deterministic_hash_v1:d512` 和 collection
`kb_chunks_trusted_validation_hash_d512_v1`。切换 Real BGE、启用 Rerank 或更换 collection
都会使当前 PASS_READY 失效，必须重新准入。

## 2. Canary 状态机与流程

状态机实现在 `backend/app/rag/trusted_rag_canary.py`，是无 I/O、无路由写入能力的纯评审器。

```text
LEGACY_ONLY -> SHADOW_ONLY -> CANARY_1 -> CANARY_5 -> CANARY_20 -> FULL_TRUSTED
                                    \          \           \            \
                                     +----------+-----------+------------> ROLLBACK
ROLLBACK -> LEGACY_ONLY -> SHADOW_ONLY（重新收集证据并评审）
```

规则如下：

1. 只允许逐级升档，不允许 `SHADOW_ONLY -> CANARY_5` 等跳级。
2. `LEGACY_ONLY -> SHADOW_ONLY` 不增加用户可见 Trusted 流量，可保持权重 0。
3. 任何非零权重升档都要求 `quality_gate.status=PASS_READY`、观测窗口完整且样本数不少于 100。
4. 处于非零权重状态时，任一回滚阈值越界，评审器优先返回 `ROLLBACK/0`，不再执行原升档请求。
5. `ROLLBACK` 只能先恢复到 `LEGACY_ONLY`；重新进入 Canary 必须重新经过 Shadow 和逐级评审。
6. 状态机的返回值只是控制面建议；本阶段没有执行该建议的生产适配器。

## 3. Canary 策略协议与权重

`CanaryPolicyProtocol` 固定包含：

- `current_state`：当前评审状态；
- `target_weight`：Trusted 用户可见流量比例，取值 `[0,1]`；
- `quality_gate`：`PASS_READY/BLOCK`、Gate 版本和阻断原因；
- `rollback_condition`：error、timeout、P95、质量退化和最小观测样本阈值。

状态与权重严格绑定，协议校验会拒绝不一致值。

| 状态 | Trusted 权重 | 进入条件 |
|---|---:|---|
| `LEGACY_ONLY` | 0 | 默认安全态 |
| `SHADOW_ONLY` | 0 | 只旁路观测，不影响用户结果 |
| `CANARY_1` | 0.01 | PASS_READY + ≥100 条本档观测 + 人工批准 |
| `CANARY_5` | 0.05 | 1% 窗口无回滚项 + 人工批准 |
| `CANARY_20` | 0.20 | 5% 窗口无回滚项 + 人工批准 |
| `FULL_TRUSTED` | 1.00 | 20% 窗口无回滚项 + 最终人工批准 |
| `ROLLBACK` | 0 | 自动回滚触发后的审计态 |

建议每一档至少覆盖 100 条且完整覆盖五类 query type；100 条只是代码中的最低评审门槛，
生产变更单可按流量规模要求更长时间窗。用户/租户分桶应使用稳定散列，避免同一用户跨档漂移；
白名单、内部账号和故障演练流量不得混入正式质量窗口。

## 4. 自动回滚机制

默认阈值沿用冻结 Gate 的硬门，并增加相对冻结基线的质量退化线：

| 触发项 | 自动回滚条件 | 原因码 |
|---|---|---|
| Error rate | `> 2%` | `rollback.error_rate_exceeded` |
| Timeout rate | `> 1%` | `rollback.timeout_rate_exceeded` |
| Latency P95 | `> 1500 ms` | `rollback.latency_p95_exceeded` |
| Quality regression | relevance/support/completeness/source coverage 任一较本档基线下降 `> 0.05` | `rollback.quality_regression:<metric>` |

边界值等于阈值不触发，超过才触发。多个条件同时越界时全部原因均保留，便于审计。
非零权重状态触发后，目标态固定为 `ROLLBACK`、建议权重固定为 0；未来生产控制面必须采用
独立于 Trusted RAG 的开关，并保证即使 Trusted 链路挂死也能恢复 Legacy。

回滚后的操作顺序建议为：权重归零 → 验证 Legacy 用户路径 → 保留指标与 traceId → 定位故障 →
人工确认进入 `LEGACY_ONLY` → 重新 Shadow。禁止故障恢复后直接回到原 Canary 档位。

## 5. 风险说明

1. 当前性能证据是单机 CPU 离线数据，尚未覆盖生产并发、资源争用、冷启动和长窗口 P99。
2. 125 条冻结样本不能替代真实 Canary 用户分布，尤其要关注操作步骤类的 relevance/support。
3. 质量指标需要人工标注，检测天然慢于 error/timeout；真实控制面应使用快慢两条回滚链路。
4. Hash Profile 的 PASS_READY 不能外推到 Real BGE；Embedding Profile 漂移必须 fail-closed。
5. RerankPolicy v1 仍须全禁用，重新启用属于新策略版本和新准入任务。
6. 本阶段只有决策协议，没有生产执行器、持久化、告警通知或审批系统，不能声称已经具备自动切流能力。

## 6. E4-C 评审结论

状态机、逐级权重、Gate 阻断和四类回滚规则具备可测试设计。建议结论为
**DESIGN_READY / PRODUCTION_NOT_ENABLED**：可以把本协议作为后续生产控制面变更评审输入，
但在独立批准、目标环境并发验证和回滚演练完成前，继续保持 `LEGACY_ONLY`、权重 0。
