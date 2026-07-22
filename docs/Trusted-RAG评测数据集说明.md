# Trusted RAG 评测数据集说明

> 数据文件：`backend/evaluation/trusted_rag_shadow_dataset.json`
>
> 版本：`trusted-rag-shadow-representative-v1`
>
> 性质：Representative Evaluation Dataset，**不是生产 Shadow 请求数据**。

## 1. 数据集定位

当前仓库没有经过授权、脱敏并持久化的真实生产请求。TASK-004-A 因此不伪造生产来源，而是基于 `backend/seed_docs/` 的 30 篇教学语料，准备一份可冻结、可校验的代表性评测集。

该数据集用于验证后续 Benchmark、Rerank 盲测和 Gate 工具能否正确消费五类样本。它不能证明真实用户分布、线上性能或生产 Shadow 质量已经达标，也不能据此将 Trusted RAG 从 Legacy 权威路径切换到生产路径。

机器可读元数据通过以下字段强制表达这个边界：

- `datasetType = representative_evaluation_dataset`；
- `productionShadowData = false`；
- `provenance.containsProductionQueries = false`；
- 每条质量标签的 `reviewStatus = pending_independent_human_review`。

## 2. 规模与分类

数据集共 100 条，每类 20 条：

| category | 中文类别 | 数量 | 期望行为 |
|---|---|---:|---|
| `concept_explanation` | 概念解释 | 20 | 给出有证据支持的定义或原理 |
| `process_explanation` | 流程说明 | 20 | 给出顺序正确、步骤完整的流程 |
| `code_technical` | 代码/技术问题 | 20 | 回答公式、配置或工程判断问题 |
| `multi_hop_reasoning` | 多跳推理 | 20 | 综合两个或以上知识点形成结论 |
| `no_answer_refusal` | 无答案拒答 | 20 | 明确证据不足，不编造答案 |

前四类直接引用仓库语料；无答案类选择知识库主题范围外、实时性、敏感性或缺少可信证据的问题，用于验证 fail-closed 拒答行为。

## 3. 数据结构

顶层结构包含：

- `datasetVersion`：冻结版本；
- `datasetType`、`productionShadowData`：来源性质与生产数据声明；
- `provenance`：语料路径、生产请求状态、PII 状态和复核状态；
- `categoryRequirements`：五类名称与最低数量；
- `caseCount`、`cases`：样本总数与样本列表。

每条 case 包含：

| 字段 | 含义 |
|---|---|
| `caseId` | 数据集内唯一标识 |
| `query` | 代表性用户问题 |
| `category` | 五类枚举之一 |
| `standardAnswer` | 基于当前语料的参考答案，或明确拒答文本 |
| `expectedEvidence` | 期望文档、仓库路径及其支持范围 |
| `answerable` / `refusal` | 可回答与应拒答的互斥标签 |
| `correctnessCriteria` | 必须覆盖的概念和正确性判定规则 |
| `evidenceCoverageCriteria` | 必须覆盖的文档、最低命中数和覆盖规则 |
| `difficulty` | `easy`、`medium` 或 `hard` |
| `qualityLabel` | 预期行为、接地要求、策划方式与复核状态 |
| `datasetVersion` | case 所属冻结版本 |

## 4. 正确性与 Evidence Coverage 口径

可回答样本必须同时满足：

1. 回答覆盖 `correctnessCriteria.requiredConcepts`；
2. 回答不与 `standardAnswer` 或 Evidence 矛盾；
3. 引用覆盖 `evidenceCoverageCriteria.requiredDocumentIds`；
4. Evidence 能直接支持所要求的核心概念。

拒答样本必须同时满足：

1. `answerable=false` 且 `refusal=true`；
2. 不声明期望领域 Evidence；
3. 回答明确说明当前知识库证据不足；
4. 不编造事实、数值、实时状态、凭据或操作步骤。

标准答案只是评测参考，不应按全文字符串相等评分。后续应采用明确概念覆盖、Evidence 引用和独立人工盲审相结合的方式。

## 5. 数据来源与人工复核边界

本版本由仓库内已知语料策划代表性问题和质量判定结构，未采集手机号、邮箱、用户标识、会话正文或其他生产请求信息。自动测试会检查五类数量、字段完整性、Evidence 文件存在性、拒答约束和明显 PII 模式。

`pending_independent_human_review` 表示这些标签尚未经过独立人工盲审。后续若取得真实请求，必须：

1. 获得合法授权并在进入仓库前完成脱敏；
2. 使用新的 dataset version，禁止覆盖本版本或混淆来源；
3. 将生产请求与代表性样本分层统计；
4. 记录采样时间窗、来源系统和脱敏规则，但不保存个人身份信息；
5. 由独立标注者复核标准答案、Evidence 和拒答标签。

在这些条件完成前，Gate 必须继续报告“真实生产 Shadow 数据缺失”，Legacy 始终保持生产权威路径。

## 6. 校验方式

```bash
cd backend
python -m pytest -q tests/test_trusted_rag_shadow_dataset.py
```

本数据集和测试均为离线文件，不会导入或调用 API、Workflow、Legacy Agent、Trusted RAG Service 或前端。
