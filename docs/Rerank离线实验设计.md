# Rerank 离线实验设计

## 1. 实验目标与边界

TASK-003-D3-A 只建立 Rerank 抽象和离线实验基础设施，用固定 Hybrid Retrieval 候选评估“只改变排序”的潜在价值。本阶段不引入真实 Rerank 模型，不接入生产 Pipeline，不修改 Agent、Workflow 或 API。

仓库已有供历史业务服务调用的 `Reranker`。本任务保留该实现及调用关系不变，在 `app/rag/reranker.py` 内新增独立的 `BaseReranker`、`RerankResult` 和 `MockReranker`，避免离线实验影响生产行为。

## 2. 接口与结果协议

`BaseReranker.rerank(query, candidates)` 接收查询文本和有序的 `RetrievalCandidate` 序列，返回完整的 `RerankResult` 列表。结果字段为：

- `candidate_id`：候选唯一 ID；
- `original_rank`：固定候选集中的原始名次，从 1 开始；
- `rerank_rank`：重排后的名次，从 1 开始且连续；
- `original_score`：Hybrid Retrieval 的原始 confidence score；
- `rerank_score`：Reranker 给出的比较分数。

离线评测器强制校验输出与输入候选 ID 集合完全一致、无增删，并要求新名次连续且不重复。这样 Rerank 只能改变顺序和用于比较的分数，不能混入召回变化。

## 3. 候选固定策略

每条 TASK-003-C2 查询先由当前 Hash Embedding Profile 下的 `HybridRetriever.search(..., top_k=20)` 生成候选。候选在 Reranker 调用前转换并冻结为 `FixedCandidateCase`，Baseline 和 Rerank 共用同一份对象快照。

固定策略为：

1. 数据集固定为 `backend/evaluation/retrieval_cases.json` 的 40 条；
2. Collection 固定为 `kb_chunks__hash_d512__utf8_v2`；
3. Embedding Profile 固定为 `hash:deterministic_hash_v1:d512`；
4. 每条查询最多保留当前 Hybrid Retrieval 输出 Top20，保持其 scope filter、相关性治理和候选顺序；
5. Baseline 直接按固定候选顺序计算，Rerank 只按 `rerank_rank` 重排同一候选集合。

如果 Hybrid 治理后不足 20 条，不用无关内容补齐；“Top20”表示上限而不是强制填满。无答案用例不参与 MRR、nDCG 和 Top1 的均值，沿用 TASK-003-C2 指标口径。

## 4. 指标说明

- MRR：首个相关候选名次的倒数均值，反映首个有效证据前移程度；
- nDCG@3：考虑人工相关度等级的前三位排序质量；
- nDCG@5：考虑人工相关度等级的前五位排序质量；
- Top1：`HitRate@1`，第一位是否命中相关证据；
- 排序变化案例：仅输出至少一个候选发生位移的 case，并记录原名次、新名次和前后分数。

报告同时给出 Baseline、Rerank 和 `Rerank - Baseline` 差值，防止只报告相对变化而缺少绝对基线。

## 5. Mock 实验结果

运行命令：

```powershell
cd backend
python scripts/evaluate_rerank.py --collection kb_chunks__hash_d512__utf8_v2
```

40 条 C2 数据实测结果：

| 指标 | Baseline | Mock Rerank | 变化 |
|---|---:|---:|---:|
| MRR | 0.735714 | 0.735714 | 0.000000 |
| nDCG@3 | 0.646784 | 0.646784 | 0.000000 |
| nDCG@5 | 0.670110 | 0.670110 | 0.000000 |
| Top1 | 0.628571 | 0.628571 | 0.000000 |

排序变化案例为 0。`MockReranker` 是恒等映射，原样保留顺序和 confidence score，因此本结果只证明实验链路正确，不代表 Rerank 模型没有优化空间，也不得解释为模型收益。

## 6. 后续模型接入方案

TASK-003-D3-B 可新增一个只实现 `BaseReranker` 的离线适配器，将 `(query, candidate.content)` 批量送入待评测模型，再把模型分数稳定映射为完整 `RerankResult`。建议：

1. 先保存固定候选快照及其数据、Collection、Embedding Profile 指纹，真实模型与 Mock 共用快照；
2. 模型名称、版本、权重校验值、设备、批大小和推理耗时写入实验报告；
3. 相同分数用 `original_rank` 稳定打破平局；
4. 同时报告总体指标、按 query type 分层指标、正负排序变化案例和推理时延；
5. 在独立验证集复验并完成回归检查前，继续保持 offline/shadow-only，不接入生产流程。

当前 Hash Profile 的结果不能外推到 Real BGE；恢复真实 Embedding 后必须重新冻结候选并单独报告。
