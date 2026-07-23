# Trusted RAG QualityGate v2 指标定义

> 冻结任务：TASK-004-E4-B
> 版本：`quality-gate-v2`
> 生效范围：Trusted RAG 离线准入评估；不代表 Canary 已启用。

## 1. 设计结论

QualityGate v2 使用 `relevance`、`support_rate`、`completeness`、
`source_coverage` 四个互补指标作为硬门。`evidence_overlap` 只衡量 Trusted 与 Legacy
返回来源集合的一致程度，不能区分“Trusted 改善了 Legacy”与“Trusted 偏离正确答案”，
因此冻结为 diagnostic，不再单独阻断质量门。`confidence` 同样保留为诊断值，不替代标注质量。

四项硬指标必须同时达到阈值；缺失、评审未完成、样本不足或 request id 不一致均 fail-closed。

## 2. 指标与阈值

| 指标 | 冻结定义 | 聚合方式 | 阈值 |
|---|---|---|---:|
| relevance | Evidence 与 held-out expected document 的相关程度；单条评分归一化到 `[0,1]` | 全部 Evidence record 宏平均 | ≥ 0.67 |
| support_rate | 每个请求是否至少存在一条可支撑答案的 Evidence | 支撑请求数 / 全部请求数 | ≥ 0.80 |
| completeness | Evidence 对 required concepts 的覆盖程度；评分归一化到 `[0,1]` | 全部 Evidence record 宏平均 | ≥ 0.30 |
| source_coverage | 返回 Evidence 的有效、去重来源覆盖程度 | 请求级 coverage 均值 | ≥ 0.80 |

`relevance=0.67` 的语义是每三条已评 Evidence 至少约两条相关；它与 request-level
`support_rate` 不重复。`completeness=0.30` 是当前检索片段粒度下的最低可用覆盖线，不能解释为
答案完整度已达到 30%。阈值变更必须发布新 Gate 版本，禁止在同一版本内按评测结果漂移。

## 3. Diagnostic 指标

| 指标 | 定义 | 使用方式 |
|---|---|---|
| evidence_overlap | Trusted 与 Legacy Top document id 集合的 Jaccard overlap | 观察迁移差异、排查异常突变；不得作为唯一质量结论 |
| confidence | 检索内部相对置信强度 | 观察校准漂移；不得解释为答案正确概率 |

诊断指标必须进入 Gate snapshot 和冻结报告，但没有 v2 硬阈值。若未来需要把 overlap
作为稳定性约束，应新增独立 Stability Gate，而不是重新混入答案质量定义。

## 4. 当前冻结实测

125 条 held-out 请求得到：relevance `0.697143`、support_rate `0.856000`、
completeness `0.314286`、source_coverage `1.000000`，四项 PASS；
evidence_overlap diagnostic 为 `0.303010`。

操作步骤分层 relevance `0.453333`、support `0.640000`，低于总体线。v2 当前按总体准入，
该分层风险不改写本次机器 Gate 结果，但必须作为 TASK-004-E4-C 的重点 Shadow 观察项。
