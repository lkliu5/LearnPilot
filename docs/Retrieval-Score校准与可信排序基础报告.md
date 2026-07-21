# Retrieval Score校准与可信排序基础报告

> 任务：TASK-003-D2-A
> 基线提交：`7f43b4b`
> 评测集：TASK-003-C1原始8条用例
> Embedding：Hash Fallback；Real BGE未参与

## 1. 修改文件

- `backend/app/core/config.py`
- `backend/app/rag/protocol.py`
- `backend/app/rag/retriever.py`
- `backend/app/rag/pipeline.py`
- `backend/app/rag/evaluation.py`
- `backend/app/rag/evaluation_protocol.py`
- `backend/scripts/evaluate_retrieval.py`
- `backend/tests/test_hybrid_retrieval_optimization.py`
- `backend/tests/test_trusted_retrieval_pipeline.py`
- `backend/tests/test_retrieval_evaluation.py`
- `docs/Retrieval-Score校准与可信排序基础报告.md`
- `docs/progress/TASK-003-D2-A.md`

未修改Agent、Workflow、API或业务服务，未引入Rerank模型。

## 2. Score设计说明

`RetrievalCandidate`统一保存以下评分：

| 字段 | 含义 | 是否可跨Query比较 |
|---|---|---|
| `dense_score` | 向量库返回的原始相似度 | 否；受Embedding Profile和语料影响 |
| `keyword_score` | BM25原始分 | 否；受Query长度和语料统计影响 |
| `normalized_dense_score` | 当前Query候选池内Dense min-max值 | 否；仅表示池内相对位置 |
| `normalized_keyword_score` | 当前Query候选池内BM25 min-max值 | 否；仅表示池内相对位置 |
| `fusion_score` | D1加权RRF原始分 | 不建议；依赖候选池与`rrf_k` |
| `confidence_score` | 三路相对信号的配置化加权结果 | 否；是检索强度，不是正确概率 |

Min-max规则：

```text
normalized = (score - min) / (max - min)
```

当一列全部相等时，正值统一为1，零值统一为0，避免除零并保留“有信号/无信号”语义。

Confidence计算：

```text
confidence =
  (dense_weight × normalized_dense
   + keyword_weight × normalized_keyword
   + fusion_weight × normalized_fusion)
  / weight_sum
```

所有权重来自配置，负权重或总和为0时显式失败。C1校准后的默认值：

| 配置 | 值 |
|---|---:|
| `retrieval_confidence_dense_weight` | 0.10 |
| `retrieval_confidence_keyword_weight` | 0.05 |
| `retrieval_confidence_fusion_weight` | 0.85 |

选择过程只比较少量可解释组合，并要求Recall、MRR和nDCG均不低于D1。Fusion保持主导是因为它已经综合两路排名，Dense/BM25归一分作为小幅区分信号；0.4/0.3/0.3初始组合在模糊表达用例上把次相关证据提升到首位，已被拒绝。

## 3. Trust协议说明

每条`EvidenceItem`新增：

- `score_breakdown`：Dense、Keyword、两项归一分、Fusion及Confidence的完整拆分。
- `reason_codes`：与本次检索判断相关的原因码。

`RAGResponse`新增：

- `evidence_count`：最终Evidence数量。
- `source_count`：唯一文档来源数。
- `reason_codes`：响应级原因码。

原因码：

| 原因码 | 触发条件 |
|---|---|
| `NO_EVIDENCE` | 最终Evidence为空 |
| `LOW_SCORE` | 候选未通过相关性门禁，最终为空 |
| `SINGLE_SOURCE` | 非空结果仅来自一个文档 |
| `FILTERED_RESULT` | 带metadata filter的请求最终为空 |
| `OUT_OF_SCOPE` | 带knowledge scope的请求最终为空 |

Pipeline空结果仍返回`retrievalDecision=low_confidence`，不会强行生成。当前原因码是检索阶段事实摘要，不是最终Trust决策。

## 4. C1指标变化

对比命令：

```powershell
cd backend
python scripts/evaluate_retrieval.py --dataset evaluation/retrieval_cases_c1.json --collection kb_chunks__hash_d512__utf8_v2 --embedding-mode hash --compare-d1 --steady-rounds 10
```

D1与D2-A均通过Trusted Pipeline，使用相同候选池、过滤、门禁、去重和来源治理；唯一变量为Fusion排序与Confidence校准排序。

| 指标 | D1 baseline | D2-A | 变化 |
|---|---:|---:|---:|
| Recall@1 | 0.5476 | 0.5476 | 0 |
| Recall@3 | 0.9286 | 0.9286 | 0 |
| Recall@5 | 0.9286 | 0.9286 | 0 |
| MRR | 0.9286 | 0.9286 | 0 |
| nDCG@1 | 0.7755 | 0.7755 | 0 |
| nDCG@3 | 0.8524 | 0.8524 | 0 |
| nDCG@5 | 0.8524 | 0.8524 | 0 |
| EmptyResultRate | 0.1250 | 0.1250 | 0 |
| SourceCoverage | 0.7458 | 0.7458 | 0 |
| SourceCompleteness | 1.0000 | 1.0000 | 0 |

`SourceCoverage`定义为每次结果的“唯一文档数/结果数”，空结果不虚构来源缺失，计为1并由EmptyResultRate独立衡量。

## 5. Confidence分布

| 统计量 | D1原始Fusion分 | D2-A Confidence |
|---|---:|---:|
| Min | 0.0046 | 0.0891 |
| Mean | 0.0153 | 0.9037 |
| P50 | 0.0160 | 0.9581 |
| P95 | 0.0164 | 1.0000 |
| Max | 0.0164 | 1.0000 |

D1数值是原始RRF分，D2-A是Query内相对归一后的组合分，两列量纲不同，不能把数值增大解释为质量提升。D2分布明显偏高且接近饱和，原因是只统计通过门禁后的Top Evidence；这再次说明`confidence_score`不是概率，也暂不适合直接作为跨Query全局阈值。

## 6. 结论边界与D2-B建议

- C1只有8条，权重仅能视为不回退的初始配置。
- 当前为Hash Embedding，不能外推Real BGE评分分布。
- Min-max是Query内校准，尚未形成跨Query、跨Collection或跨Profile可比标尺。
- 原始分与拆分字段已经稳定，可供后续Rerank和Trust Evaluation消费。

TASK-003-D2-B建议：

1. 使用C2 40条集建立按Embedding Profile隔离的分位数/温度校准，不复用Hash阈值到BGE。
2. 将“门禁前候选数、被filter数量、低Dense数量、低Keyword数量”结构化输出，使原因码可精确区分，而非只根据最终空结果推断。
3. 增加Confidence可靠性分析，例如分桶命中率和ECE；在完成前禁止把Confidence称为正确概率。
4. 为多来源综合问题单独评估SourceCoverage与相关来源覆盖，避免简单多样性比例掩盖无关来源。
5. 后续接入Rerank时新增独立`rerank_score`，不得覆盖当前任何原始或校准字段。
