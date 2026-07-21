# RAG检索评测基线报告

> 任务：TASK-003-C1 可信检索评测基线与影子对比  
> 代码基线：`8e72794`  
> 评测日期：2026-07-21  
> 数据集：`trusted-rag-baseline-v1`

# 1 评测数据说明

## 1.1 数据来源

评测集来自仓库`backend/seed_docs/`中的30篇人工可读教学文档，包括神经网络、Transformer、机器学习、CNN以及大模型微调等主题。期望文档和切片ID依据文件编号、标题与正文人工标注，不使用随机结果或当前检索输出反推标签。

本次实际运行的Chroma `kb_chunks`包含147个切片，Embedding Profile为：

```text
sentence-transformers:baai_bge_small_zh_v1_5:d512
```

评测运行时本地Torch DLL加载受到权限限制，Embedder按既有机制降级为512维确定性哈希Embedding。该状态是本次基线的重要环境条件，不能与真实BGE语义检索结果混为一谈。

当前Chroma部分中文正文和来源标题呈现历史编码乱码。ID和来源字段结构仍可读取，但Dense语义、BM25中文词面匹配和人工内容查看均受到显著影响。

## 1.2 用例规模

共8条静态用例，每类1条：

| 类型 | case_id | 主要期望 |
|---|---|---|
| 概念解释 | concept_self_attention | doc_022、doc_002 |
| 方法比较 | compare_supervised_unsupervised | doc_005、doc_006 |
| 操作步骤 | steps_kmeans | doc_006#2 |
| 事实查询 | fact_position_encoding | doc_024、doc_002#3 |
| 跨段落综合 | synthesis_transformer_components | doc_023、doc_024、doc_025 |
| 模糊表达 | fuzzy_memorizes_answers | doc_008、doc_003#2 |
| 无答案问题 | no_answer_quantum | 无相关Evidence |
| knowledge_scope过滤 | scope_lora_only | doc_028 |

每条用例包含Query、查询类型、期望文档/切片、期望关键词、knowledge_scope、相关性等级和人工备注。数据文件位于`backend/evaluation/retrieval_cases.json`。

# 2 指标定义

- Recall@K：前K个结果覆盖的人工相关Evidence比例。
- HitRate@K：前K个结果是否至少命中一个人工相关Evidence。
- MRR：第一个相关结果排名的倒数。
- nDCG@K：根据1至3级人工相关性计算的折损累计增益。
- EmptyResultRate：返回空结果的用例比例。
- SourceCompleteness：结果中同时具备文档ID和标题或位置字段的比例，只评价结构完整性，不评价来源真实性。
- P50/P95延迟：单进程本地调用墙钟耗时分位数。
- Overlap@K：新旧Top-K共同切片数相对Top-K并集规模的比例。

无答案用例没有相关文档，Recall、HitRate、MRR和nDCG没有数学意义，报告中明确为`null/不可计算`，不按0分参与监督指标平均。

Pipeline的`confidence`仍是最高检索分的启发式摘要，元数据明确标记为`heuristic_max_retrieval_score_not_probability`，本报告不将其解释为答案正确概率。

# 3 当前基线结果

## 3.1 汇总指标

| 指标 | HybridRetriever | TrustedRetrievalPipeline |
|---|---:|---:|
| Recall@1 | 0.0000 | 0.0000 |
| Recall@3 | 0.0714 | 0.0714 |
| Recall@5 | 0.0714 | 0.0714 |
| HitRate@1 | 0.0000 | 0.0000 |
| HitRate@3 | 0.1429 | 0.1429 |
| HitRate@5 | 0.1429 | 0.1429 |
| MRR | 0.0476 | 0.0476 |
| nDCG@1 | 0.0000 | 0.0000 |
| nDCG@3 | 0.0241 | 0.0241 |
| nDCG@5 | 0.0449 | 0.0449 |
| EmptyResultRate | 0.0000 | 0.0000 |
| SourceCompleteness | 1.0000 | 1.0000 |
| P50延迟 | 10.2232 ms | 9.7780 ms |
| P95延迟 | 545.6561 ms | 10.8768 ms |

指标只代表上述本地数据快照和降级Embedding环境。当前质量明显不足：7条有答案用例中仅1条在Top-5命中部分期望Evidence。

## 3.2 用例结果

- `concept_self_attention`：Top-5命中`doc_002`，Recall@5为0.5，第一个相关结果排第3，MRR为0.3333。
- 其余6条有答案用例：Recall@5和MRR均为0。
- `no_answer_quantum`：仍返回5条不相关结果，说明当前系统没有相关性阈值或拒答机制；监督排序指标标记不可计算。
- `scope_lora_only`：没有召回`doc_028`，且knowledge_scope未影响结果，符合当前“只进入QueryPlan、不执行过滤”的已知边界。

# 4 新旧Pipeline对比

8条用例的新旧`Overlap@5`均为1.0，召回文档、切片顺序和底层分数完全一致。这是预期结果：TASK-003-B2只统一协议和Evidence转换，Pipeline内部仍调用同一个HybridRetriever，没有修改检索算法。

差异主要是：

- 旧结果为松散候选字典；新结果统一为`EvidenceItem`。
- Pipeline把chunk、document、title和location整理为`source`，但来源结构完整率与旧结果相同，均为1.0。
- Pipeline增加QueryPlan、阶段耗时、候选数、Evidence数和空结果标记。
- 分数未重新排序，只按`score → rrfScore → vectorScore`顺序映射；Evidence协议保留4位小数，因此共同切片的新旧分数差仅为舍入误差，实测绝对值不超过0.000045。

延迟不能据表格断言Pipeline更快。离线脚本按“旧调用在前、新调用在后”执行，共享同一个Retriever；首条旧调用承担模型加载失败与索引预热成本，造成旧P95异常升高。后续应交替执行顺序、预热后多轮测量并拆分冷启动与稳态数据。

# 5 失败案例分析

## 5.1 环境降级与历史编码问题

本次最大影响因素是BGE模型未成功加载，Dense Retrieval退化为哈希向量；同时Chroma中的部分中文内容已经乱码，BM25无法用正常中文Query匹配原词。这两项足以解释大面积错误召回。在评估RRF权重或引入新Reranker之前，应先完成语料重新入库并确认真实BGE可用。

## 5.2 无答案查询必然返回结果

Retriever固定返回Top-K，没有最低相关性阈值、Evidence过滤或拒答判断，因此量子纠错问题仍获得5条教学内容。EmptyResultRate为0并不代表覆盖好，而是说明系统无法表达“知识库无答案”。

## 5.3 跨文档综合召回失败

Transformer综合问题需要同时覆盖多头注意力、位置编码和编码器解码器三个文档，当前Top-5未命中任何期望文档。后续需要查询拆解、多查询召回、来源多样性和重排，而不是只增加单路Top-K。

## 5.4 模糊表达失败

“像背答案一样”是过拟合的教学类比。当前未命中精确的`doc_008`或`doc_003#2`，说明降级Embedding和乱码BM25无法完成语义归一。Query理解应将模糊表述扩展为“过拟合、泛化、正则化”。

## 5.5 knowledge_scope尚未生效

Pipeline已经把scope放入QueryPlan filters，但旧Retriever接口只接受query与top_k，没有执行文档过滤。因此该用例用于稳定暴露功能差距，不应通过修改期望结果掩盖。

# 6 后续Rerank和Trust优化依据

优化顺序应基于本基线逐层推进：

1. 数据环境治理：以UTF-8原始seed_docs重新切片入库，验证文档ID、正文和来源位置无乱码。
2. Embedding运行治理：解决Torch加载权限，分别记录真实BGE与哈希降级基线。
3. Query理解：对比较、模糊表达和跨段落综合生成关键词与子查询。
4. Scope过滤：在召回前执行document/category/knowledge scope过滤。
5. Candidate与Rerank：扩大候选池后统一重排，并增加文档多样性约束。
6. Context Filtering：增加最低相关性阈值，让无答案问题产生空Evidence/Fallback。
7. Trust Evaluation：结合召回覆盖、来源完整、引用支持和降级状态；不得把当前confidence直接当概率。

每次优化后使用同一版本评测集复跑，并同时保存环境、Embedding Profile、Collection版本和冷/热启动标记。

# 7 当前评测局限

- 仅8条用例，每类只有1条，不能代表完整用户分布。
- ID依据seed_docs编号约定；重新入库若改变ID，需要版本化更新标签。
- 部分期望同时采用文档级和切片级粒度，相关性仍需第二位标注者复核。
- 未评价生成答案、Claim支持和Citation正确性。
- SourceCompleteness只检查字段存在，不检查内容编码、来源权威性或引用支持度。
- 当前Top-5没有经过Reranker；本阶段按要求未引入新模型。
- 本次延迟是单进程、单轮顺序执行，包含明显冷启动顺序偏差。
- 当前知识库乱码和Embedding降级使结果主要反映环境故障下限，而非理想算法上限。

复现命令：

```bash
cd backend
python scripts/evaluate_retrieval.py --output retrieval-baseline.json
```

该入口只读知识库并生成离线JSON报告，不接入生产API，也不影响业务响应。
