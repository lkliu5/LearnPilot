# Trusted RAG Shadow 数据集报告

> 任务：TASK-004-E3-A Trusted RAG Shadow 数据集冻结
>
> 前置：TASK-004-E2（`21e0df9`）
>
> 边界：仅构建离线评估数据；未修改生产入口、Agent 业务逻辑或 Canary 权重。

## 1. 数据来源

冻结文件为 `backend/evaluation/trusted_rag_shadow_e3a_frozen.json`，schema 为
`trusted-rag-shadow-evaluation-v2`。采样脚本读取 TASK-004-A 已评审代表性用例，
在本地 `kb_chunks` 集合上实际执行 Legacy Retriever 与 Trusted RAG Pipeline，
只保留两条检索路径产生的指标，不复制 query、用户身份、Evidence/知识正文。

冻结窗口为 `2026-07-22T09:46:30Z`，运行环境标记为
`local-offline-shadow-measurement`。本批数据是真实代码路径的离线执行结果，
不是 Mock 指标，也不是生产 Shadow 流量；因此 `performance_verified=false`，
不能单独作为生产环境延迟准入证据。

## 2. 分层策略

采用五层等额采样，每层 20 条：

| query_type | 中文类型 | 数量 | 来源规则 |
|---|---|---:|---|
| `concept_explanation` | 概念解释 | 20 | 概念解释代表性用例 |
| `method_comparison` | 方法比较 | 20 | 从概念、流程、技术用例中人工策划的比较/选择类 case id，独立重跑 |
| `operation_steps` | 操作步骤 | 20 | 流程说明代表性用例 |
| `programming_practice` | 编程实践 | 20 | 代码/技术代表性用例 |
| `comprehensive_question` | 综合问题 | 20 | 多跳推理代表性用例 |

方法比较属于稀缺层，采用独立请求重跑方式过采样；request id 由任务版本、分层、
case id 和序号做 SHA-256 派生，冻结结果中不保留源 case id 或 query。

## 3. 数据规模与校验

- 总样本数：100；五类各 20，分层覆盖通过。
- P95 总延迟：45.0323 ms；Timeout 0，Error 0。
- Evidence overlap 均值：0.068238；Source coverage 均值：0.676；Confidence 均值：0.265792。
- 完整性检查：`valid=true`，错误列表为空。

完整性规则同时覆盖：必需字段、request id 唯一性、五类枚举及每类最小样本数、
延迟非负、质量指标 `[0, 1]` 范围、Timeout 原因一致性。任一必需指标组缺失、
重复 request、未知类型、覆盖不足或越界值都会阻断 schema/freeze 校验。

## 4. 隐私处理

每条样本只允许以下四类信息：

- `request_id`、`query_type`；
- `latency_metrics`、`quality_metrics`、`reliability_metrics`；
- `gate_features`（指标完整性和目标环境来源事实）。

Pydantic 模型使用 `extra="forbid"`；测试明确验证 `query`、`user_identity`、
`knowledge_content` 等字段会被拒绝。冻结 JSON 也经过关键字段扫描，不包含 query
正文、用户身份、知识/Evidence 正文或异常消息。

## 5. Gate 用途

`TrustedRAGGate` 可直接聚合该数据集的质量均值、P95、Timeout/Error rate 和类型分布。
数据完整性及可靠性可用于 E3-B 的准入证据输入，但当前数据明确不是目标部署环境样本，
且质量均值低于现有 Gate 阈值，所以不能据此开启 Canary。当前正确动作仍是保持 Legacy、
Canary 权重为零。

E3-B 建议在目标部署环境沿用 v2 schema 采集新冻结窗口，保持五类各不少于 20 条，
完成独立人工质量复核并查明 Evidence overlap、Source coverage、Confidence 偏低原因；
随后连同已完成的故障注入证据和 Rerank 复核结果重跑 Gate。只有四个子 Gate 全部 PASS，
才提交最小流量 Canary 的独立变更评审。
