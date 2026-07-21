# Real Reranker 离线实验报告

## 1. 实验环境

- 范围：TASK-003-D3-B，仅 offline/shadow；未接入生产 Pipeline。
- 系统：Windows 11，Python 3.12.13，CPU 推理（无 CUDA）。
- 依赖：sentence-transformers 5.6.0，torch 2.13.0+cpu。
- 参数：batch_size=8，max_length=512。
- 数据：`backend/evaluation/retrieval_cases.json` 40 条；其中 35 条有答案，指标均值沿用既有口径排除 5 条无答案用例。

## 2. 模型信息

- model_name：`BAAI/bge-reranker-base`
- model_version：`2cfc18c9415c912f9d8155881c133215df768a70`
- weight_hash：`sha256:ced967c45fd1902eb92716c9ceeca7c95a936770ea9db611f5a841b926e33fbd`
- 权重来源：本地 Hugging Face cache；实验强制 `local_files_only=True`，加载失败即实验失败，不回退 Mock。
- 适配器：`RealCrossEncoderReranker(BaseReranker)`，保持 `query + candidates` 输入与完整 `RerankResult` 输出协议；同分时按原始名次稳定打破平局。

## 3. 候选固定方式

在 Hash Embedding Profile `hash:deterministic_hash_v1:d512` 和 collection `kb_chunks__hash_d512__utf8_v2` 上，对每个 query 只执行一次 `HybridRetriever.search(top_k=20)`。快照在真实 Reranker 推理前写入 `backend/evaluation/rerank_real_candidates_d3b.json`，逐条包含 query_id、query_type、embedding_profile、collection 和完整候选列表。Baseline 与 Real Reranker 共用同一对象快照，实验只改变排序，不改变召回。

## 4. 指标变化

| 指标 | Baseline | Real Reranker | 变化 |
|---|---:|---:|---:|
| MRR | 0.735714 | 0.763810 | +0.028096 |
| nDCG@3 | 0.646784 | 0.655782 | +0.008998 |
| nDCG@5 | 0.670110 | 0.684249 | +0.014139 |
| Top1 accuracy | 0.628571 | 0.714286 | +0.085715 |

40 条中有 20 条发生排序变化，共 78 个候选发生位移。

任务要求的五类 query type 分层如下（单元格为 Real - Baseline）：

| Query type | MRR | nDCG@3 | nDCG@5 | Top1 |
|---|---:|---:|---:|---:|
| 概念解释 | +0.250000 | +0.224901 | +0.138766 | +0.400000 |
| 方法比较 | +0.040000 | -0.003557 | +0.043883 | +0.200000 |
| 操作步骤 | -0.100000 | -0.073814 | -0.073814 | -0.200000 |
| 跨段综合 | -0.033333 | +0.001028 | -0.001656 | 0.000000 |
| 模糊表达 | 0.000000 | -0.033202 | -0.033202 | 0.000000 |

完整结果还保留了事实查询、无答案问题和 knowledge_scope 过滤类型，见 `backend/evaluation/rerank_real_results_d3b.json`。

## 5. 正负排序案例

正向案例：

- `concept_neural_network`：MRR +0.75、nDCG@3 +1.00、Top1 +1.00，真实语义交叉编码有效纠正 Hash Hybrid 的首位排序。
- `compare_l1_l2`：MRR +0.50、nDCG@3/+nDCG@5 +0.36907、Top1 +1.00。
- `synthesis_mlp_training`：MRR +0.50、nDCG@3 +0.407836、Top1 +1.00。

负向案例：

- `steps_instruction_tuning`：MRR -0.50、nDCG@3/-nDCG@5 -0.36907、Top1 -1.00，是操作步骤类型整体退化的关键案例。
- `fact_relu`：MRR -0.80、nDCG@3 -1.00、nDCG@5 -0.613147、Top1 -1.00。
- `synthesis_overfit_controls`：MRR -0.50、nDCG@5 -0.068924、Top1 -1.00。

这说明总体提升不能覆盖类型与个案回归，尤其不能据此直接替换生产排序。

## 6. 延迟分析

| 项目 | 延迟 |
|---|---:|
| 模型加载 | 5590.777 ms |
| 40 条总推理 | 44156.699 ms |
| 平均每 query | 1103.917 ms |
| 中位数每 query | 969.654 ms |
| P95 每 query | 3048.924 ms |

上述为本机 CPU、Top20、batch_size=8 的单次实测，不含 Hybrid Retrieval 时间。冷启动还需约 5.59 秒，当前延迟不适合未经预算和压测直接进入在线链路。

## 7. 是否建议接入 Pipeline

**当前不建议接入生产 Pipeline。** Real Reranker 展示了明确的总体排序价值，尤其 Top1 提升 0.085715；但 40 条数据同时用于观察和报告、没有独立验证集，且操作步骤等类型存在显著回归，CPU P95 约 3.05 秒。建议继续保持 offline/shadow-only。

TASK-003-D3-C 建议：建立独立验证集并复验置信区间；针对操作步骤、跨段综合和模糊表达设计类型门控或 baseline 回退；验证 max_length/batch_size/ONNX 或量化的质量-延迟曲线；设置“总体指标提升且各关键类型不显著退化”的上线门槛；通过 shadow 流量完成延迟与回归观测后再讨论 Pipeline 接入。

## 8. 复现命令

```powershell
cd backend
python scripts/evaluate_rerank.py --collection kb_chunks__hash_d512__utf8_v2 --snapshot evaluation/rerank_real_candidates_d3b.json --output evaluation/rerank_real_results_d3b.json --device cpu --batch-size 8 --max-length 512
pytest -q
```
