# Rerank 融合策略优化报告

## 1. 类型收益分析

实验继续复用 D3-B 的 40 条评测集、固定 Hybrid Top20 候选快照、Hash Embedding Profile 与真实 `BAAI/bge-reranker-base`。本阶段只做 offline/shadow 决策，不修改生产 Pipeline。

| Query type | Baseline MRR | Rerank MRR | ΔMRR | ΔnDCG@3 | ΔnDCG@5 | ΔTop1 |
|---|---:|---:|---:|---:|---:|---:|
| 概念解释 | 0.750000 | 1.000000 | +0.250000 | +0.224901 | +0.138766 | +0.400000 |
| 方法比较 | 0.800000 | 0.840000 | +0.040000 | -0.003557 | +0.043883 | +0.200000 |
| 操作步骤 | 0.600000 | 0.500000 | -0.100000 | -0.073814 | -0.073814 | -0.200000 |
| 跨段综合 | 0.600000 | 0.566667 | -0.033333 | +0.001028 | -0.001656 | 0.000000 |
| 模糊表达 | 0.600000 | 0.600000 | 0.000000 | -0.033202 | -0.033202 | 0.000000 |

概念解释是唯一四项指标全部稳定为正的目标类型。方法比较虽有总体收益，但 nDCG@3 与个案存在回归；操作步骤明确退化；跨段综合和模糊表达没有稳定收益。因此 conditional 只选择概念解释，属于保守的探索性 Gate。

## 2. Gate 策略

新增离线协议 `RerankDecision`：

- `enabled`：本次是否执行真实 Rerank；
- `reason`：决策或降级原因；
- `query_type`：评测 query 类型；
- `confidence`：Hybrid 候选最高 retrieval confidence，仅表示检索相对强度，不解释为正确概率。

支持三种策略：

| 策略 | 行为 | 用途 |
|---|---|---|
| `always` | 全部执行 Rerank | Hybrid + Rerank 对照组 |
| `never` | 全部保留 Hybrid 顺序 | Hybrid Only 基线与强制降级 |
| `conditional` | `query_type=概念解释` 且 `confidence>=0.9883` 才执行 | 保守 shadow 候选策略 |

`0.9883` 沿用 D2-B shadow threshold，但它与类型选择都来自相同 40 条数据，存在明显过拟合风险。模型推理异常时，离线决策器记录 `reranker_error_hybrid_fallback` 并恢复 Hybrid 原顺序。未来若进入工程验证，还应在调用外围增加硬超时、并发上限和熔断；本阶段不改生产实现。

## 3. Shadow 策略结果

| 策略 | 启用数 | MRR | nDCG@3 | nDCG@5 | Top1 | 推理总耗时 |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid Only (`never`) | 0/40 | 0.735714 | 0.646784 | 0.670110 | 0.628571 | 0 ms |
| Hybrid + Rerank (`always`, 4×256) | 40/40 | 0.767619 | 0.668729 | 0.690974 | 0.714286 | 28101.911 ms |
| Conditional | 5/40 | 0.771429 | 0.678913 | 0.689934 | 0.685714 | 5819.349 ms |

Conditional 相对 Hybrid Only：MRR +0.035715、nDCG@3 +0.032129、nDCG@5 +0.019824、Top1 +0.057143。它减少 87.5% 的 Rerank 调用数，实测总推理耗时比 always 减少约 79.3%。由于启用的 5 条概念解释文本长度分布不同，不能直接用其单 query 均值与全量均值做无偏比较。

## 4. 延迟优化实验

真实 CPU 实验，固定相同 40 条候选；模型加载时间不计入推理总耗时。

| batch size | max_length | MRR | nDCG@3 | nDCG@5 | 总推理 ms | 均值 ms | P95 ms |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 256 | 0.767619 | 0.668729 | 0.690974 | 28101.911 | 702.548 | 1330.845 |
| 8 | 256 | 0.767619 | 0.668729 | 0.690974 | 30899.530 | 772.488 | 1706.847 |
| 4 | 512 | 0.763810 | 0.655782 | 0.684249 | 38336.158 | 958.404 | 2572.039 |
| 8 | 512 | 0.763810 | 0.655782 | 0.684249 | 44541.942 | 1113.549 | 3208.948 |

本机 CPU 上 `batch_size=4, max_length=256` 最优：相对 8×512 总推理耗时降低约 36.9%，三项排序指标没有下降。该结果可能受 CPU、文本长度和单次运行波动影响，不能外推到 GPU 或生产并发。

## 5. 退化案例

Always 策略仍有 7 个综合指标为负的排序案例：

- `compare_classification_regression`
- `steps_instruction_tuning`
- `fact_relu`
- `synthesis_cnn_components`
- `synthesis_transformer_components`
- `synthesis_overfit_controls`
- `fuzzy_memorizes_answers`

Conditional 本次模拟为 0 个退化案例，因为上述用例均不属于已验证的概念解释类型。这个“0”是当前小样本上的观察值，不代表真实流量零回归。

## 6. 推荐接入策略

当前仍不建议直接接入生产 Pipeline。建议保留如下候选方案进入后续独立 shadow 验证：

1. 默认 Hybrid Only；仅对独立验证后确认获益的类型开放 conditional Rerank。
2. 初始实验参数采用 CPU `batch_size=4, max_length=256`；生产硬件上重新压测。
3. 模型不可用、推理异常、超时、队列超限或熔断时无条件回退 Hybrid，并记录 reason。
4. 监控 Gate 启用率、类型分布、增量 P50/P95、回退率与退化 case；不把 retrieval confidence 当正确概率。
5. 只有独立集与真实 shadow 流量都满足“总体提升、关键类型不退化、延迟预算达标”后，才提交生产接入评审。

## 7. TASK-003-E 建议

建立独立、盲标的验证集并扩充五类 query；冻结 Gate v1 后只在新数据上验收，避免继续拟合当前 40 条。并行完成分类器误判分析、置信度重新校准、CPU/GPU/量化压测、超时与熔断故障注入。TASK-003-E 仍建议先做 shadow observability 与上线门槛，不直接改生产排序。

完整机器可读结果：`backend/evaluation/rerank_shadow_results_d3c.json`。
