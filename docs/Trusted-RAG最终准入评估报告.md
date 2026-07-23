# Trusted RAG 最终准入评估报告

> 任务：TASK-004-E4-A Trusted RAG 最终准入验证
>
> 前置：TASK-004-E3-C（`d4622ee`）
>
> 评估时间：2026-07-23
>
> 边界：仅离线验证；未修改生产入口、Agent/Workflow 业务流程，Canary 权重保持 0。

## 1. Validation 数据说明

本轮新增 `TrustedRAGValidationDataset`，冻结文件为
`backend/evaluation/trusted_rag_validation_dataset.json`，schema 为
`trusted-rag-validation-v1`。数据集共 125 条，五类各 25 条：

| 类型 | 数量 |
|---|---:|
| 概念解释 | 25 |
| 方法比较 | 25 |
| 操作步骤 | 25 |
| 编程实践 | 25 |
| 综合问题 | 25 |

每条样本包含独立 case id、query、expected document ids 和 required concepts。数据由
25 个知识主题与五类任务矩阵独立策划，不读取 E3-C 优化结果生成问句。评估器对 E3 的
100 条原始 query 和本集 125 条 query 分别做规范化 SHA-256 指纹校验，重合数为 **0**；
case id、规范化 query 唯一性和每层不少于 20 条均由 Pydantic schema 强制校验。

本集是 held-out 离线验证集，不是生产 Shadow 流量，也没有用于调整 E3-C 检索参数。

## 2. Quality 结果

总体 Evidence 复评结果：

| 指标 | 结果 | Gate 阈值/性质 | 判定 |
|---|---:|---:|---|
| Relevance | 0.701657 | ≥0.70 | PASS |
| Support rate | 0.896000 | ≥0.80 | PASS |
| Completeness | 0.316759 | 观察项 | 低，需继续补强 |
| Source coverage | 1.000000 | ≥0.80 | PASS |
| Evidence overlap | 0.057410 | ≥0.70 | **BLOCK** |
| Confidence | 1.000000 | ≥0.80 | PASS |

Completeness 按 Evidence 对 required concepts 的覆盖程度评分；分层表中的 completeness
表示 expected document coverage，因此两者语义不同，不能直接互换。

| 类型 | Relevance | Support | Expected-doc completeness | Source coverage | Evidence overlap |
|---|---:|---:|---:|---:|---:|
| 概念解释 | 0.780000 | 0.880000 | 0.880000 | 1.000000 | 0.042667 |
| 方法比较 | 0.906667 | 1.000000 | 0.640000 | 1.000000 | 0.050000 |
| 操作步骤 | 0.506667 | 0.760000 | 0.760000 | 1.000000 | 0.121333 |
| 编程实践 | 0.713333 | 0.880000 | 0.880000 | 1.000000 | 0.028000 |
| 综合问题 | 0.873333 | 0.960000 | 0.640000 | 1.000000 | 0.045048 |

操作步骤仍是最弱分层，relevance 和 support 均低于总体准入线。125/125 请求都触发了
EvidenceQualityGate 的 keyword fallback，说明当前主 Hybrid 结果没有一次直接通过保护门；
虽然 fallback 能把总体 relevance/support 拉到阈值附近，但不能视为主检索已稳定。

Evidence overlap 再次与 expected relevance 呈明显冲突：Trusted 输出经来源去重和近最优
keyword 过滤后，与 Legacy 的 Top document set 重合很低。现行 Gate 将 overlap 定义为硬
阈值，因此不能以 relevance 已通过为由忽略该阻断，也不能在本任务内下调 0.70 阈值。

## 3. Embedding Profile 核验

| 字段 | 核验值 |
|---|---|
| collection | `kb_chunks` |
| profile_id | `hash:deterministic_hash_v1:d512` |
| dimension | 512 |
| stored dimension | 512 |
| embedding_mode | `hash_fallback` |
| 明确分类 | **Hash，不是 Real BGE** |

集合现有 metadata 只声明 `hnsw:space=cosine`，缺少 provider、model、dimension 和
profile_id 四项完整声明；本轮通过实际向量读取核验 stored dimension 为 512。此次结果只能
证明 512 维确定性 Hash query 与现有集合可执行，不能证明 Real BGE collection profile 已
完成目标环境准入核验。

## 4. Latency 结果

| 指标 | 结果 |
|---|---:|
| 样本数 | 125 |
| P50 | 22.880900 ms |
| P95 | 26.405200 ms |
| Timeout | 0 / 125（0%） |
| Error | 0 / 125（0%） |
| Fallback 触发 | 125 / 125 |
| Fallback overhead mean | 0.176618 ms |
| Fallback overhead P95 | 0.276100 ms |

所有请求均在 1500 ms hard deadline 内完成，Legacy 保持不受影响。该窗口来自
`local-offline-final-validation`，`performance_verified=false`，因此数值虽显著低于
1500 ms 阈值，Gate 仍按 fail-closed 规则输出
`latency.performance_not_verified`。本地离线 P95 不冒充目标部署环境 P95。

## 5. Reliability 结果

- Validation：0 timeout、0 error，Legacy preserved=true，timeout isolation=true。
- E2 故障注入证据：11 个场景全部 PASS，fault failure rate=0。
- Reliability 子 Gate：**PASS**。

本任务没有接入生产路由，也没有执行 Canary 切流或回滚动作。

## 6. Rerank 结果

本轮在 125 条独立验证样本上使用本地缓存的 `BAAI/bge-reranker-base`（CPU、batch=4、
max_length=256）复核。模型加载 2837.099 ms，单 query inference P95 为 630.740 ms。

| 策略 | MRR | nDCG@3 | nDCG@5 | 相对 Hybrid delta |
|---|---:|---:|---:|---|
| Never / Hybrid | 0.830667 | 0.747414 | 0.747414 | 基线 |
| Always | 0.820000 | 0.739746 | 0.739746 | -0.010667 / -0.007668 / -0.007668 |
| Conditional | 0.826667 | 0.744462 | 0.744462 | -0.004000 / -0.002952 / -0.002952 |

Always Rerank 出现 8 个退化 case，其中操作步骤 1 个、综合问题 1 个、概念解释 2 个、
编程实践 4 个。Conditional 规则仅允许概念解释且 confidence ≥0.9883，共启用 25 条，
仍有 2 个退化 case，三项聚合 delta 仍为负。

结论：**保留 conditional 作为后续唯一可继续收紧的策略方向，但当前规则不具备启用条件，
运行态应继续等价于 Never/Hybrid。禁止改为 Always。** 还需独立人工偏好/相关性复核；
本轮 `metrics_provisional=true`、`human_review_complete=false`，不把自动 expected-document
标签伪装成人工复核结果。

## 7. Gate 最终状态

机器可读结果：`backend/evaluation/trusted_rag_gate_decision_e4a.json`。

| 子 Gate | E3-C | E4-A | 变化 |
|---|---|---|---|
| Quality | BLOCK | BLOCK | 仍由 Evidence overlap 阻断；独立集 relevance/support 通过 |
| Latency | BLOCK | BLOCK | 已有 P50/P95/timeout/fallback 数据，但非目标环境 |
| Reliability | PASS | PASS | 维持通过 |
| Rerank | BLOCK | BLOCK | 独立实跑完成，但 conditional 仍退化且人工复核未完成 |
| Final | BLOCK | **BLOCK** | 无准入状态变化 |

最终结构化阻断原因：

1. `quality.evidence_overlap_below_threshold`
2. `latency.performance_not_verified`
3. `rerank.metrics_still_provisional`
4. `rerank.human_review_incomplete`
5. `rerank.mrr_regressed`
6. `rerank.ndcg_at_3_regressed`
7. `rerank.ndcg_at_5_regressed`
8. `rerank.degraded_cases_exceeded`

Gate 推荐动作仍为 `keep_legacy_and_set_canary_weight_to_zero`。Canary 未开启。

## 8. Canary 建议与 TASK-004-E4-B

**当前不满足进入 Canary 评审条件。** E4-B 建议限定为“准入阻断项关闭”，仍禁止切流：

1. 对独立集 overlap 与 expected relevance 冲突做逐 case 双人复核，冻结 overlap 的安全语义；
   如需变更指标，单独版本化 Gate，而不是直接降阈值。
2. 使用 Real BGE 重建独立 validation collection，补齐 collection 的 provider/model/
   dimension/profile_id metadata，并验证 query/collection profile 完全一致。
3. 在目标部署环境复跑 125+ 条同分层样本，设置 `performance_verified=true` 的前提是全部
   样本确实来自该环境；复核 P50/P95、timeout 和 fallback overhead。
4. 对 2 个 conditional 退化 case 及操作步骤、综合问题做双人盲审；收紧类型/置信度规则，
   直至 MRR、nDCG@3、nDCG@5 均不退化且 degraded case=0。
5. 只有 Quality、Latency、Reliability、Rerank 四门全部 PASS，才另立 Canary 评审任务；
   E4-B 自身仍不修改生产入口或 Canary 权重。
