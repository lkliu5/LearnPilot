# RAG Confidence 校准报告

## 1. 评估口径

- 任务：TASK-003-D2-B，离线验证 D2-A 的 retrieval confidence；未引入 Rerank，未修改 Agent、Workflow、API。
- 数据：TASK-003-C2 人工评测集，共 40 条，8 类查询各 5 条；其中 35 条有答案、5 条无答案。
- Embedding Profile：`hash:deterministic_hash_v1:d512`。Real BGE 仍沿用 C3-A 的 blocked 结论，本报告不生成或冒充 BGE 结果。
- Collection：`kb_chunks__hash_d512__utf8_v2`。
- 正样本定义：有答案用例的 `HitRate@5=1`；无答案用例目标为 0。该定义评估的是“Top-5 是否存在人工相关证据”，不是最终答案是否正确。
- Confidence 语义：D2-A 的归一化检索相对强度，不是正确概率。ECE 仅用于暴露分数与上述二元目标之间的偏差。

## 2. Confidence 分布与分桶结果

| Confidence 桶 | Case 数 | 平均 Confidence | 正样本率 | HitRate@5 | Recall@5 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| 0–0.2 | 6 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 0.2–0.4 | 0 | — | — | — | — | — |
| 0.4–0.6 | 0 | — | — | — | — | — |
| 0.6–0.8 | 0 | — | — | — | — | — |
| 0.8–1.0 | 34 | 0.9884 | 0.8824 | 0.8824 | 0.7770 | 0.7574 |

无答案用例参与 Case 数、正样本率和 ECE；其排序指标为不可计算值，不作为 0 混入 HitRate/Recall/MRR 均值。当前分数高度两极化，中间三个桶没有样本，说明现有 confidence 能分离“无结果”和“有结果”，但对高分候选的细粒度可信度区分不足。

## 3. ECE 结果

采用固定五桶 ECE：

`ECE = Σ (桶样本数 / 总样本数) × |桶平均 confidence - 桶正样本率|`

实测 ECE 为 **0.09014**。该数值依赖本次 Hash Embedding Profile、40 条数据和 HitRate@5 标签定义，不能跨 Embedding Profile 复用，也不能解释为“错误概率为 9.014%”。

## 4. 阈值建议与 Shadow Gate

离线遍历本数据集已观测 confidence，以 balanced accuracy 为目标，得到建议阈值 **0.9883**：

- Balanced Accuracy：0.8667
- True Positive Rate：0.9333
- True Negative Rate：0.8000
- Shadow pass：30/40（75%）
- Shadow block：10/40（25%）

阈值被封装为独立 `CalibrationProfile`：

```json
{
  "profile_id": "hash:deterministic_hash_v1:d512",
  "threshold": 0.9883,
  "calibration_version": "hash-c2-40-v1"
}
```

Shadow Gate 只记录 pass/block，不改变检索结果或真实回答流程。0.9883 是同一 40 条数据上选择并评估的探索性阈值，存在明显过拟合风险；在独立验证集确认前不得作为生产门禁。

## 5. Calibration 与 Trust 协议

`CalibrationProfile` 包含 `profile_id`、`threshold`、`calibration_version`，阈值必须由评测调用显式提供，未设置全局默认阈值。

`TrustReport` 是检索阶段快照，包含：

- `retrieval_confidence`：当前检索相对强度；
- `evidence_count`、`source_count`：证据与独立来源数量；
- `coverage`：`source_count / evidence_count`；
- `reason_codes`：沿用 `NO_EVIDENCE`、`LOW_SCORE`、`SINGLE_SOURCE`、`FILTERED_RESULT`、`OUT_OF_SCOPE`。

它不代表最终答案可信度，也不替代事实核验。为保持接口范围不变，本阶段只扩展 RAG 内部协议和离线评测输出。

## 6. 当前限制

1. 40 条数据规模仍小，且阈值选择与指标报告共用同一数据集，没有训练/验证隔离。
2. 仅验证 Hash fallback；Real BGE blocked，因此阈值不得迁移到真实 BGE Profile。
3. D2-A 采用查询内 min-max，最高候选容易接近 1，造成高分饱和和空桶。
4. `HitRate@5` 只表示召回命中，不覆盖证据忠实度、答案生成正确性或安全性。
5. 无答案标签只有 5 条，True Negative Rate 方差较大。
6. 当前 ECE 为固定分桶估计，空桶与样本不均衡会降低解释稳定性。

## 7. 后续 Rerank 需求与阶段结论

建议进入 TASK-003-D3，但应把它定义为离线 Rerank 实验和独立评测，而不是直接上线：

- 固定候选集与 Hash 基线，避免同时改变召回和排序；
- 增加独立验证集，分离阈值拟合与报告；
- 比较 Rerank 前后的 Recall、MRR、nDCG、ECE 及失败案例；
- Real BGE 恢复后必须建立新的 CalibrationProfile，禁止复用 Hash 阈值；
- 在进入真实门禁前继续保持 shadow-only。

结论：已具备进入 D3 离线实验的协议和诊断基础，但尚不具备启用生产 confidence 门禁的条件。
