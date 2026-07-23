# Trusted RAG 质量优化报告

> 任务：TASK-004-E3-C Trusted RAG Evidence 质量优化
>
> 前置：TASK-004-E3-B（`8420e15`）
>
> 边界：仅优化检索与 Evidence 治理并进行离线 Shadow 复评；未开启 Canary，未修改 Agent、Workflow 或 API。

## 1. 优化范围与方法

本轮保持 E3-A 冻结集的 100 个 opaque request id 和五类各 20 条分层不变，使用与 E3-B
相同的本地离线环境、知识库集合、确定性 hash embedding 和人工策划 expected document
标准。优化后另存 `trusted_rag_shadow_e3c_optimized.json` 和
`trusted_rag_quality_e3c.json`，不覆盖 E3-A/E3-B 基线。

实现了四项检索层优化：

1. 新增 `EvidenceQualityGate`，在 Evidence 构建前保护 Top3，检查 keyword relevance、
   source count 和 support；任一不足即触发 fallback。
2. Keyword 检索由单一字符 BM25 改为字段化组合：正文字符 BM25 权重 2.0、正文三元短语
   BM25 权重 0.25、标题/章节二元短语 BM25 权重 2.0。该方式仍为本地确定性检索，不依赖
   LLM 或 API Key。
3. 增加来源多样性：Top 结果优先选择不同 document，fallback 每个 document 最多保留
   一条，只保留 keyword 分数达到首条 90% 的候选，避免低相关片段为凑 Top3 而进入 Evidence。
4. Hybrid 结果未通过质量门时执行 Keyword fallback，并重新运行同一质量门；fallback
   只有通过或在 relevance/source/support 三项上严格改善时才能替换原结果。

## 2. 22 条空 Evidence 归因

归因协议：先验证 expected document 是否存在于当前 29 个文档的语料，再检查 expected
document 是否进入 dense/sparse 候选池，最后检查 scope/metadata filter 与治理结果。结果如下：

| 分类 | 数量 | 占 22 条比例 | 判定 |
|---|---:|---:|---|
| 真无答案 | 0 | 0% | expected document 均存在于语料 |
| 检索失败 | 22 | 100% | expected document 已进入 20 条候选池，但被原 relevance 治理淘汰 |
| scope 过滤失败 | 0 | 0% | 冻结集未出现错误 scope 排除 |
| Query 理解失败 | 0 | 0% | 没有 expected document 在 dense/sparse 候选池同时缺失的 case |

分层为：概念解释 2、方法比较 4、操作步骤 4、编程实践 6、综合问题 6。优化后 100 条
request 的空 Evidence 数为 0。该结论仅适用于本次全为可回答问题的冻结集；线上未知问题
仍应 fail-closed，不能把“本集空结果清零”解释为任何 query 都必须返回 Evidence。

## 3. 100 条 Shadow 前后对比

| 指标 | E3-B 优化前 | E3-C 优化后 | 变化 | Gate 阈值 |
|---|---:|---:|---:|---:|
| Evidence overlap | 0.068238 | 0.063500 | -0.004738 | ≥0.70 |
| Source coverage | 0.676000 | 1.000000 | +0.324000 | ≥0.80 |
| Confidence | 0.265792 | 0.972780 | +0.706988 | ≥0.80 |
| Human relevance | 0.271084 | 0.705426 | +0.434342 | ≥0.70 |
| Support rate | 0.320000 | 0.870000 | +0.550000 | ≥0.80 |
| Completeness | 0.218876 | 0.322997 | +0.104121 | 观察项 |
| 空 Evidence request | 22 | 0 | -22 | 观察项 |
| Evidence 记录数 | 166 | 129 | -37 | — |

Evidence 数下降不是召回退化：策略主动丢弃未达到首条 keyword 分数 90% 的低相关候选，
因此 relevance、support 与 completeness 同时上升。Source coverage 达到 1.0，表示每条返回
Evidence 都来自不同 document；它不表示知识库覆盖了所有可能答案。

分层复评：

| 类型 | Evidence 数 | Human relevance | Support rate | Completeness | Source coverage |
|---|---:|---:|---:|---:|---:|
| 概念解释 | 23 | 0.826087 | 0.95 | 0.463768 | 1.00 |
| 方法比较 | 25 | 0.680000 | 0.80 | 0.320000 | 1.00 |
| 操作步骤 | 25 | 0.720000 | 0.90 | 0.333333 | 1.00 |
| 编程实践 | 27 | 0.555556 | 0.70 | 0.197531 | 1.00 |
| 综合问题 | 29 | 0.758621 | 1.00 | 0.321839 | 1.00 |

编程实践仍是最弱分层，E4 不应据总体均值忽略该局部风险。

## 4. Gate 变化与 Quality Pass 可能性

Quality 子 Gate 仍为 **BLOCK**，但质量阻断原因从 5 项降为 1 项：

- 已解除：`quality.source_coverage_below_threshold`
- 已解除：`quality.confidence_below_threshold`
- 已解除：`quality.human_relevance_below_threshold`
- 已解除：`quality.support_rate_below_threshold`
- 仍阻断：`quality.evidence_overlap_below_threshold`

Evidence overlap 略降而人工 relevance/support 大幅上升，说明当前“与 Legacy document set
重合”的指标和“命中人工 expected evidence”在此基线上方向不一致。不能为通过 Gate 调低
0.70 阈值；应在独立集上审计 Legacy 基线、明确 overlap 的安全含义，并决定它应作为稳定性
约束还是答案质量约束。

离线 Gate 复评结果仍为 `final_decision=BLOCK`：Quality BLOCK、Latency BLOCK、
Reliability PASS、Rerank BLOCK。除 overlap 外，仍有目标环境性能未验证、Rerank 指标仍为
provisional、人工复核未完成和 2 个退化 case。Canary 权重保持 0，本任务没有开启 Canary。

## 5. 验证结果

复评命令：

```powershell
cd backend
python scripts/freeze_trusted_rag_shadow_dataset.py --output evaluation/trusted_rag_shadow_e3c_optimized.json
python scripts/evaluate_trusted_rag_quality.py --shadow-dataset evaluation/trusted_rag_shadow_e3c_optimized.json --output evaluation/trusted_rag_quality_e3c.json
python scripts/evaluate_trusted_rag_gate.py --shadow-metrics evaluation/trusted_rag_shadow_e3c_optimized.json --quality-results evaluation/trusted_rag_quality_e3c.json --output evaluation/trusted_rag_gate_decision_e3c.json
pytest -q -p no:cacheprovider --basetemp .pytest_task004_e3c_full
```

专项测试实测：`32 passed in 0.67s`。全量测试实测：
`438 passed, 1 skipped, 1 warning in 143.44s`；warning 为既有 FastAPI TestClient 的
Starlette 弃用提示，不是测试错误。

## 6. TASK-004-E4 建议

1. 冻结独立验证集，优先补强编程实践和方法比较，不复用 E3-C 调参集作最终准入结论。
2. 对 Legacy overlap 与 expected relevance 的冲突做逐 case 双人复核；如需调整指标定义，
   应单独评审 Gate 语义和版本，不能直接降低阈值。
3. 使用实际 BGE embedding profile 重建/校验向量集合，记录 collection profile，避免 hash
   query 与历史向量空间来源不明；Mock/hash 路径仍须保留并可全链路运行。
4. 完成独立 Rerank 人工相关性/偏好复核，维持操作步骤和综合问题不启用 always rerank，
   复验 2 个退化 case。
5. 在目标部署环境重跑 100+ 分层 Shadow，验证 P95、Timeout/Error 与 fallback 开销。
   Quality、Latency、Reliability、Rerank 四门全部 PASS 后，才另立 Canary 评审任务。
