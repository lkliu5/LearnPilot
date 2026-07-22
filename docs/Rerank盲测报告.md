# Rerank 独立盲测报告

> 任务：TASK-004-C Trusted RAG Rerank 独立盲测验证
>
> 数据集：`backend/evaluation/rerank_blind_dataset.json`
>
> 结果：`backend/evaluation/rerank_blind_results.json`
>
> 最终结论：**BLOCK**。

## 1. 独立性与盲测设计

本次新建 `rerank-blind-independent-v1`，包含 20 条 query、每条 5 个固定候选，共 100 个候选。它不复用 TASK-003 的 40 条 query、`rerank_real_candidates_d3b.json` 候选快照或 D3-C 策略选择结果。

自动测试将本数据集 query 与 TASK-003 `retrieval_cases.json` 做标准化精确比对，重合数为 0。数据集同时冻结以下声明：

- `independentFromTask003=true`；
- `task003CandidateSnapshotReused=false`；
- `candidateIdsAnonymized=true`；
- `candidateSnapshotFrozen=true`。

每条候选对 Reranker 只暴露：

- 匿名 ID，例如 `RB01-A7K2`；
- 固定正文；
- 冻结 Baseline rank。

真实文档映射、相关性等级和人工偏好状态位于独立评分区。评估模块构造 `RetrievalCandidate` 时强制使用空 `source` 和空 `metadata`，模型无法读取文档 ID、相关性标签或 Human Preference。

## 2. 人工评价状态

当前没有完成独立人工盲标：

| 项目 | 状态 |
|---|---|
| relevance labels | `pending_independent_human_review` |
| Human Preference | `pending_independent_human_review` |
| 已复核 preference | 0 / 20 |
| 自动推断 Human Preference | 禁止，未执行 |

因此：

- 所有 Recall/MRR/nDCG 结果标记为 `metricsProvisional=true`；
- `humanPreference.rerankPreferenceRate=null`；
- `gateEvidence.independentValidation=false`；
- 无论自动指标是否提升，最终准入都必须为 BLOCK。

## 3. 真实 Reranker 环境

| 项目 | 实测值 |
|---|---|
| model | `BAAI/bge-reranker-base` |
| revision | `2cfc18c9415c912f9d8155881c133215df768a70` |
| weight SHA-256 | `ced967c45fd1902eb92716c9ceeca7c95a936770ea9db611f5a841b926e33fbd` |
| device | CPU |
| batch size | 4 |
| max length | 256 |
| model load | 4989.515 ms |
| inference total | 13523.681 ms |
| inference mean | 676.184 ms/query |
| inference P95 | 828.989 ms/query |
| runtime | CPython 3.12.13 / Windows 11 |

该结果由本地缓存真实模型生成，没有用 `MockReranker` 替代。模型只负责排序；指标由冻结标签计算，不存在模型给自己的回答打分。以上延迟为本机单进程 CPU 离线结果，并设置 `productionPerformance=false`。

## 4. 自动排序指标

| 指标 | Baseline | Rerank | Delta |
|---|---:|---:|---:|
| Recall@1 | 0.141667 | 0.591667 | +0.450000 |
| Recall@3 | 0.608333 | 0.925000 | +0.316667 |
| Recall@5 | 1.000000 | 1.000000 | 0.000000 |
| MRR | 0.564167 | 1.000000 | +0.435833 |
| nDCG@3 | 0.267762 | 0.971078 | +0.703316 |
| nDCG@5 | 0.510888 | 0.979257 | +0.468369 |

这些结果显示真实 Reranker 在当前冻结标签上总体提升明显，但标签仍待独立人工复核，不能作为最终人工质量结论。

## 5. Human Preference

```text
status: pending_independent_human_review
reviewedCount: 0
totalCount: 20
baseline: 0
rerank: 0
tie: 0
rerankPreferenceRate: null
```

评估器不会根据 MRR、nDCG 或模型分数自动填充 Human Preference。后续人工盲审必须隐藏系统身份，对 Baseline/Rerank 排序分别审阅，再由独立 reviewer 填写 `baseline`、`rerank` 或 `tie`。

## 6. 退化案例

严格规则是任一监控指标 delta 小于 0 即记为退化。本次发现 2 条：

| caseId | 退化指标 |
|---|---|
| `t004c_blind_11` | Recall@3 |
| `t004c_blind_20` | Recall@3 |

这两条的高等级相关项排名改善，但次相关项移出 Top-3，导致 Recall@3 下降。即使总体 MRR/nDCG 提升，退化案例仍单独阻断，不能被平均值掩盖。

## 7. Gate 结论

最终为 **BLOCK**，结构化原因：

1. `rerank.relevance_labels_pending_independent_human_review`；
2. `rerank.human_preference_pending_independent_human_review`；
3. `rerank.degraded_cases_present`。

兼容已有 Gate 的证据摘要为：

```text
independentValidation = false
mrrDelta = 0.435833
ndcgAt3Delta = 0.703316
ndcgAt5Delta = 0.468369
degradedCaseCount = 2
```

本阶段没有修改已有 Gate，也没有把该结果接入生产路由。Legacy 继续保持生产权威路径。

## 8. 复现命令

真实模型需要允许本地 Torch DLL 加载。本次运行命令为：

```powershell
cd backend
$env:PYTHONPATH='F:\软件杯\backend\.bge-c3a-venv\Lib\site-packages'
& 'C:\Users\力恺\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/evaluate_rerank_blind.py `
  --dataset evaluation/rerank_blind_dataset.json `
  --output evaluation/rerank_blind_results.json `
  --model BAAI/bge-reranker-base `
  --device cpu `
  --batch-size 4 `
  --max-length 256
```

在没有独立人工盲标结果时，禁止手工把输出中的 `finalDecision` 改为 PASS。
