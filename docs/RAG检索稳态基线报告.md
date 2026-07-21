# RAG检索稳态基线报告

> 任务：TASK-003-C2  
> 数据集：`trusted-rag-baseline-v2`  
> Collection：`kb_chunks__hash_d512__utf8_v2`
> 日期：2026-07-21

# 1 评测集规模和来源

评测集扩展为40条，标签来自30篇AI教学文档；重建范围覆盖全部35篇UTF-8源文档（另含5篇网络文档），共178个干净切片。八类查询各5条：

| 查询类型 | 数量 |
|---|---:|
| 概念解释 | 5 |
| 方法比较 | 5 |
| 操作步骤 | 5 |
| 事实查询 | 5 |
| 跨段落综合 | 5 |
| 模糊表达 | 5 |
| 无答案问题 | 5 |
| knowledge_scope过滤 | 5 |

期望文档、切片、关键词和Evidence依据均来自`seed_docs`人工声明，未根据Retriever输出反推。

# 2 标注状态

每条用例新增：

- `annotator`
- `annotation_status`
- `evidence_basis`
- `difficulty`
- `second_annotator`

当前40条均由第一标注者完成结构化整理，状态全部为`pending_second_review`，`second_annotator=null`。项目尚未获得真实第二人复核，因此不报告双人一致率，也不伪造`double_reviewed`状态。

数据集验证已通过：

- case_id重复：0
- Query重复：0
- 冲突标注：0
- 失效document ID：0
- 失效chunk ID：0

# 3 Hash Fallback基线

Embedding运行状态：

```text
mode: hash_fallback
profile: hash:deterministic_hash_v1:d512
dimension: 512
loadError: null
```

35条有答案用例参与Recall/HitRate/MRR/nDCG平均；5条无答案用例的监督排序指标为不可计算，不按0混入。

| 指标 | HybridRetriever | Trusted Pipeline |
|---|---:|---:|
| Recall@1 | 0.4619 | 0.4619 |
| Recall@3 | 0.8357 | 0.8357 |
| Recall@5 | 0.8905 | 0.8905 |
| HitRate@1 | 0.6000 | 0.6000 |
| HitRate@3 | 0.9143 | 0.9143 |
| HitRate@5 | 0.9429 | 0.9429 |
| MRR | 0.7581 | 0.7581 |
| nDCG@1 | 0.5184 | 0.5184 |
| nDCG@3 | 0.7181 | 0.7181 |
| nDCG@5 | 0.7439 | 0.7439 |
| EmptyResultRate | 0.0000 | 0.0000 |
| SourceCompleteness | 1.0000 | 1.0000 |
| 评测循环P50 | 9.7491 ms | 10.0874 ms |
| 评测循环P95 | 11.0582 ms | 12.2571 ms |

新旧结果平均Overlap@5为1.0。Pipeline仍是旧Retriever的协议封装，没有改变排序算法。

Hash结果提升不能解释为真实语义模型能力提升；主要变化来自干净、完整的35篇源文档重新入库，以及哈希词面信号在正常中文上的可用性。

# 4 Real BGE基线

状态：`blocked`

强制真实评测命令退出码为2，原因：

```text
PermissionError [WinError 5]
Windows loader无法加载torch_python.dll或其依赖DLL
```

文件存在且可读取，普通ACL允许当前沙箱用户修改，但动态加载仍被拒绝。真实评测启用了`allow_fallback=false`，没有生成任何Recall、MRR、nDCG或延迟数字。

因此本报告不存在“伪BGE结果”，Hash与Real状态完全分离。

# 5 冷启动与稳态延迟

测量方法：

- Cold Start：单独记录首次旧Retriever与Pipeline调用。
- Warm-up：2轮，不计入稳态统计。
- Steady State：10轮，每套系统10个样本。
- 偶数轮顺序`old → new`，奇数轮`new → old`，避免固定先后顺序。
- 使用同一Query和同一Collection，只比较封装开销，不断言通用性能。

本次Hash基线：

| 阶段/指标 | HybridRetriever | Trusted Pipeline |
|---|---:|---:|
| Cold Start | 8.5471 ms | 8.5661 ms |
| 稳态样本数 | 10 | 10 |
| 稳态均值 | 9.1727 ms | 9.6413 ms |
| 稳态中位数 | 9.1561 ms | 9.7444 ms |
| 稳态P95 | 10.1775 ms | 10.3823 ms |

样本量仍小，差值仅代表本机单进程本次运行。不得据此宣称某一入口具有稳定性能优势。
Cold Start仍在同一进程中按旧后新各执行一次，第二个调用可能复用已加载模块与Chroma客户端，因此两项冷启动数字只用于记录各自所处的首次调用位置，不用于横向性能结论；稳态阶段才使用交替顺序降低偏差。

# 6 失败案例分类

## 6.1 有答案Top-5未命中

两条用例Recall@5为0：

- `synthesis_finetuning_stack`：一次Query需要覆盖预训练、PEFT、LoRA、SFT和RLHF多个专题，单次Top-5词面召回不足。
- `fuzzy_small_adapter`：模糊表达“不改主体、加小旁路”需要语义归一为LoRA，哈希Embedding缺乏该能力。

## 6.2 无答案问题

5条无答案问题仍全部返回结果，EmptyResultRate为0。这不是优点，而是当前Retriever没有最低相关性阈值或拒答机制。

## 6.3 Scope能力边界

knowledge_scope存在于QueryPlan，但旧Retriever尚未执行过滤。部分scope用例因Query本身明确而命中，不能据此声称过滤已经生效。

# 7 当前结论边界

- 本基线只代表`hash_fallback + UTF-8 clean Collection`。
- Hash confidence是检索分启发式摘要，不是答案正确概率。
- 真实BGE不可用，无法比较Hash与真实语义Embedding。
- 40条用例尚未完成第二人复核。
- 当前未使用Rerank、Query改写或新检索算法。
- 延迟样本只覆盖单Query、单机、单进程。

# 8 是否具备进入检索算法优化阶段的条件

结论：`有条件，不建议立即开始核心算法调参`。

已经具备：

- 干净、完整、可版本化的Hash评测Collection。
- 40条可复现人工评测用例。
- 新旧影子对比和稳态延迟框架。
- 编码、维度、来源和失效ID质量门禁。

仍需满足：

1. 在独立环境修复Torch并建立真实BGE基线。
2. 完成关键用例第二人复核。
3. 扩大稳态延迟Query样本，而非只测单Query。

在此之前可以开发不改变排序的评测基础设施和scope过滤契约，但不建议基于Hash结果调整RRF权重或评价Rerank收益。
