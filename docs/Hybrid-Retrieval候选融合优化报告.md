# Hybrid Retrieval候选融合优化报告

> 任务：TASK-003-D1
> 基线提交：`70031b0`
> 评测集：TASK-003-C1原始8条用例
> Embedding：`hash_fallback`，未使用Real BGE

## 1. 修改范围

- 新增统一`RetrievalCandidate`候选协议。
- 优化`HybridRetriever`的候选池、合并、RRF和治理流程。
- Pipeline传递QueryPlan metadata filter并输出明确低置信状态。
- 新增C1原始评测集版本和旧算法离线快照，用于同进程before/after比较。
- 增加候选协议、去重、metadata filter、来源多样性、低相关性和配置测试。

未修改Agent、Workflow、API、业务服务或前端，未引入Rerank模型。

## 2. Hybrid算法变化

优化前：

```text
Dense top_k×2 + BM25 top_k×2
  → 加权RRF
  → 截取top_k
```

其中BM25即使分数为0也会进入RRF并获得排名分，知识库外查询必然返回候选；候选没有统一结构，scope只进入QueryPlan而未执行。

优化后：

```text
Query
  ├─ Dense Retrieval(candidate_top_k)
  └─ Keyword Retrieval(candidate_top_k，剔除BM25<=0)
       → Candidate Merge（chunk ID去重）
       → Weighted RRF Fusion
       → metadata filter
       → 内容去重 + 单来源配额
       → 相关性门禁
       → Evidence Ranking(final_top_k)
```

统一候选字段：`id`、`content`、`source`、`metadata`、`dense_score`、`keyword_score`、`fusion_score`。为避免破坏现有业务调用方，输出同时保留`vectorScore`、`bm25Score`、`rrfScore`兼容字段。

候选治理：

- 同一chunk在Dense和Keyword两路合并为一个候选。
- 规范化正文完全相同时只保留排名最高者。
- 默认每篇文档最多保留2个Chunk，避免单一来源垄断。
- 支持`knowledge_scope.document_ids`及普通metadata精确值/允许列表过滤。
- 无候选或全部候选低于门禁时返回空Evidence，Pipeline标记`retrievalDecision=low_confidence`和`lowConfidence=true`，不强行进入生成。

## 3. 参数选择依据

| 参数 | 默认值 | 依据 |
|---|---:|---|
| `retrieval_candidate_top_k` | 20 | 设计方案推荐候选池20；较旧`top_k×2`提供更充分的两路合并空间 |
| `rrf_k` | 60 | 延续C1既有RRF常数，D1不同时调整融合平滑常数和其他变量 |
| `retrieval_final_top_k` | 5 | 与C1 Recall/HitRate@5口径一致 |
| `retrieval_max_chunks_per_source` | 2 | 保留同文档局部覆盖，同时为跨文档证据留出位置 |
| `retrieval_min_dense_score` | 0.35 | C1 Hash观测：无答案最高约0.326，有效难例约0.369 |
| `retrieval_min_query_overlap` | 0.35 | 防止仅因哈希碰撞通过；需同时具备基本词面覆盖 |
| `retrieval_min_strong_keyword_overlap` | 0.60 | 兼容旧Collection向量空间不可比场景，强词面匹配可独立通过 |

普通查询满足“Dense与基本词面阈值”，或达到更严格的强关键词覆盖阈值时保留。后者用于旧Collection向量与当前Hash查询空间不可比但BM25证据明确的兼容场景。显式scope已提供强先验，因此允许“正BM25 + 足够词面覆盖”的范围内候选通过，避免合法scope候选被全局Dense阈值误杀。

这些值是`Hash + C1 + 当前Collection`的工程起点，不是正确概率，也不能外推为Real BGE阈值。

## 4. C1指标对比

评测命令：

```powershell
cd backend
python scripts/evaluate_retrieval.py --dataset evaluation/retrieval_cases_c1.json --collection kb_chunks__hash_d512__utf8_v2 --embedding-mode hash --compare-legacy --steady-rounds 10
```

7条有答案用例参与排序指标；无答案用例不按0混入Recall/MRR/nDCG。

| 指标 | 优化前 | 优化后 | 变化 |
|---|---:|---:|---:|
| Recall@1 | 0.4048 | 0.5476 | +0.1429 |
| Recall@3 | 0.9286 | 0.9286 | 0 |
| Recall@5 | 0.9286 | 0.9286 | 0 |
| HitRate@1 | 0.7143 | 0.8571 | +0.1429 |
| HitRate@3 | 1.0000 | 1.0000 | 0 |
| HitRate@5 | 1.0000 | 1.0000 | 0 |
| MRR | 0.8333 | 0.9286 | +0.0952 |
| nDCG@1 | 0.6327 | 0.7755 | +0.1429 |
| nDCG@3 | 0.7809 | 0.8524 | +0.0714 |
| nDCG@5 | 0.7809 | 0.8524 | +0.0714 |
| EmptyResultRate | 0.0000 | 0.1250 | +0.1250 |
| SourceCompleteness | 1.0000 | 1.0000 | 0 |

EmptyResultRate增加对应唯一的无答案用例，属于预期拒答行为；7条有答案用例均非空。空结果由EmptyResultRate衡量，SourceCompleteness只判断实际返回项是否缺少来源字段。

## 5. 失败案例与边界

- `scope_lora_only`：优化前相关文档第3名，优化后metadata filter将`doc_028`提升到第1名，是Recall@1/MRR改善的主要来源。
- `no_answer_quantum`：优化前强制返回5条无关内容，优化后返回空Evidence并标记低置信。
- C1仍只有8条，指标变化对单条用例敏感，不能作为通用线上收益结论。
- 当前Embedding为Hash，模糊语义能力有限；阈值不能直接用于Real BGE。
- Source diversity默认按文档ID计数；跨文档问题得到改善空间，但尚未做按查询类型自适应配额。
- 未进行Query改写、Rerank或RRF权重搜索，符合D1边界。

## 6. TASK-003-D2建议

建议D2聚焦“候选质量校准与查询类型策略”，不要直接引入生成侧改动：

1. 在C2 40条集和后续Real BGE基线上分别校准相关性阈值，配置按Embedding Profile隔离。
2. 采用内容指纹让BM25缓存按内容变化失效，而不是仅按Collection数量。
3. 为跨段落综合、精确事实和模糊表达分别选择候选池与来源配额。
4. 增加低置信原因码，例如`no_keyword_signal`、`dense_below_threshold`、`filtered_by_scope`。
5. 在真实BGE可用前，不根据Hash结果调整Dense/Sparse权重或评价Rerank收益。
