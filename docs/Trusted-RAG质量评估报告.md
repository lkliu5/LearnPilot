# Trusted RAG 质量评估报告

> 任务：TASK-004-E3-B Trusted RAG Evidence 质量评估与 Rerank 复核
>
> 前置：TASK-004-E3-A（`9e1bd1e`）
>
> 边界：仅离线评估与 Gate 分析；未开启 Canary，未修改生产入口或 Agent 业务流程。

## 1. 数据集说明

本次复用 E3-A 冻结的 `trusted-rag-shadow-evaluation-v2` 数据集，共 100 个 request，
五类各 20 条。评估窗口为 `2026-07-22T09:46:30Z`，环境仍是
`local-offline-shadow-measurement`，`performance_verified=false`。因此延迟数值只能用于
本地离线比较，不能充当目标部署环境的 Canary 性能证据。

人工评估协议为 `EvidenceEvaluationRecord`，每条记录只允许：`request_id`、
`evidence_rank`、`relevance_score`、`completeness_score`、`supports_answer`、
`source_quality`。四项评分采用 0–3 级量表。评估时临时读取 E3-A 的代表性 case、
人工策划的 expected document 和 required concepts，并复现 Trusted Evidence；落盘文件
只保留 opaque request id、rank、分数和布尔值，不保存 query、知识/Evidence 正文或
用户信息。结果文件为 `backend/evaluation/trusted_rag_quality_e3b.json`。

这是基于仓库人工策划标签的逐条复核；`review_complete=true` 表示 100 个 request 已按
协议完成检查，不代表进行了双人盲标或生产用户偏好实验。

## 2. Evidence 评分

### 2.1 总体结果

| 指标 | 结果 | Gate 阈值 | 结论 |
|---|---:|---:|---|
| Request 数 | 100 | ≥100 | 达标 |
| Evidence 记录数 | 166 | — | 22 个 request 无 Evidence |
| Evidence overlap | 0.068238 | ≥0.70 | 不达标 |
| Source coverage | 0.676000 | ≥0.80 | 不达标 |
| Human relevance | 0.271084 | ≥0.70 | 不达标 |
| Support rate | 0.320000 | ≥0.80 | 不达标 |
| Completeness | 0.218876 | 观察项 | 偏低 |
| Source quality | 1.000000 | 观察项 | 来源元数据完整 |

Human relevance 是全部实际 Evidence 的 `relevance_score / 3` 均值；Support rate 是
至少存在一条支持 Evidence 的 request 比例，无 Evidence request 按不支持计入。
Source quality 高说明已返回 Evidence 的 document id 与来源定位完整，但不说明 Evidence
与问题相关。当前主要问题是“来源可追溯，但召回不相关或为空”。

### 2.2 分层结果

| 类型 | Evidence 数 | 无 Evidence request | Overlap | Coverage | Human relevance | Support rate |
|---|---:|---:|---:|---:|---:|---:|
| 概念解释 | 49 | 2 | 0.084345 | 0.775833 | 0.367347 | 0.650000 |
| 方法比较 | 32 | 4 | 0.070893 | 0.710833 | 0.125000 | 0.150000 |
| 操作步骤 | 38 | 4 | 0.079643 | 0.639167 | 0.263158 | 0.300000 |
| 编程实践 | 25 | 6 | 0.037143 | 0.641667 | 0.280000 | 0.250000 |
| 综合问题 | 22 | 6 | 0.069167 | 0.612500 | 0.272727 | 0.250000 |

概念解释相对最好，但仍未达到准入线；方法比较相关性最低；编程实践与综合问题的空召回
最多。该结果与 E3-A 的低 Confidence/Overlap 相互印证，不应通过调低阈值掩盖。

## 3. Rerank 复核

复核依据为 D3-C 固定候选上的 always 与 conditional 结果，重点检查操作步骤和综合问题。

| 类型 | 总体变化 | 退化 case | 原因 |
|---|---|---|---|
| 操作步骤 | ΔMRR -0.100000；ΔnDCG@3/-@5 -0.073814；ΔTop1 -0.200000 | `steps_instruction_tuning` | Cross-encoder 将泛化训练流程片段升至 Top1，把直接 SFT Evidence 从 1 降至 2，Top1 与 MRR 同时退化。 |
| 综合问题（跨段综合） | ΔMRR -0.033333；ΔnDCG@3 +0.001028；ΔnDCG@5 -0.001656；ΔTop1 0 | `synthesis_cnn_components`、`synthesis_transformer_components`、`synthesis_overfit_controls` | 单段语义匹配压过多来源覆盖；互补 Evidence 在 Top3 内换位或被移出，导致 graded relevance 与多证据完整性下降。 |

当前 conditional 策略只对已验证的“概念解释 + confidence threshold”启用 Rerank，以上
两类均已被排除，所以本轮**不需要放宽或改写现有类型 Gate**。必须继续禁止在操作步骤和
综合问题上启用 always Rerank。若 E3-C 计划扩大类型，应先实现 Baseline Top3 高置信
Evidence 保护、多来源覆盖约束或 Hybrid fallback，再用独立集复验；不能因 conditional
当前观察到 0 个退化 case 就推断生产零回归。

## 4. Gate 变化

Gate 输入新增 `QualityEvaluationResult`，并校验：100 条评估完整性、request id 与冻结集
一致、机器 overlap/coverage 与 Shadow 聚合一致、人工相关性和支持率阈值。输出 schema
升级为 `trusted-rag-canary-gate-v3`。

| 子 Gate | E3-B 前 | E3-B 后 | 变化 |
|---|---|---|---|
| Quality | BLOCK（指标缺失） | BLOCK（五项质量指标低于阈值） | 从“缺证据”变为“有证据且不达标” |
| Latency | BLOCK | BLOCK | P95 已有 45.0323 ms，但非目标环境，仍不可验证 |
| Reliability | BLOCK（Shadow 样本缺失） | PASS | 100 条完整、Timeout/Error 0、故障注入 11/11 PASS |
| Rerank | BLOCK | BLOCK | 独立人工偏好/相关性仍 provisional，且盲测有 2 个退化 case |
| Final | BLOCK | BLOCK | 保持 Legacy，Canary weight=0 |

当前阻断原因：

- `quality.evidence_overlap_below_threshold`
- `quality.source_coverage_below_threshold`
- `quality.confidence_below_threshold`
- `quality.human_relevance_below_threshold`
- `quality.support_rate_below_threshold`
- `latency.performance_not_verified`
- `rerank.metrics_still_provisional`
- `rerank.human_review_incomplete`
- `rerank.degraded_cases_exceeded`

## 5. Canary 建议

结论为 **不进入 Canary**。E3-B 完成了准入证据补齐，但质量证据明确不达标，不能通过
降低 Gate 阈值或仅依据本地低延迟放行。继续保持生产 Legacy 权威与 Canary 权重 0。

TASK-004-E3-C 建议聚焦三项：先修复空召回及 expected document 命中，重点处理方法比较、
编程实践和综合问题；为综合问题增加多来源/Top3 Evidence 保护并复验 Rerank；最后在目标
部署环境重新冻结 100+ 条同分层 Shadow，完成独立双人相关性与偏好复核。只有 Quality、
Latency、Reliability、Rerank 四个子 Gate 全部 PASS，才提交独立的最小流量 Canary 评审。
