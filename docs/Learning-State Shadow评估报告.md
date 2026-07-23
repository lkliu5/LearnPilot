# Learning-State Shadow 评估报告

> 阶段：TASK-005-C
>
> 模式：Shadow（不替换、不回写现有 `Mastery`）
>
> 算法版本：`ks-logodds-v1`

## 1. Evidence 来源

| 来源 | 既有载体 | Adapter 入口 | 状态事件类型 | 基础权重 | 在线结果影响 |
|---|---|---|---|---:|---|
| Quiz 结果 | `QuizAttempt` | `from_quiz_result` | `quiz` | 1.00 | 无；只生成 Shadow 事件 |
| 学习诊断 | 诊断单题结果 `{kpId, correct}` | `from_diagnostic` | `diagnostic` | 0.55 | 无；不改变诊断写 Mastery 的既有链路 |
| 费曼讲解 | 费曼评估 `{score, gaps, ...}` | `from_feynman` | `feynman` | 0.70 | 无；不修改 Agent/Workflow |
| 学习步骤完成 | `LearningStepProgress` | `from_learning_step` | `learning_step` | 0.15 | 无；步骤仍与 Mastery 解耦 |

统一输出为 `LearningEvent`，协议字段为：

- `event_id`：由 `source_type + source_id` 的 SHA-256 截断值确定性生成；
- `source_type`：保留原始 Evidence 来源语义；
- `source_id`：原始记录或业务回合的稳定 ID；
- `algorithm_version`：本次状态计算规则版本；
- `user_id / knowledge_id / event_type / score / timestamp`：状态计算的规范化输入。

## 2. Event 转换规则

| Evidence | score 归一化 | source_id 建议 | 特殊规则 |
|---|---:|---|---|
| Quiz | `QuizAttempt.score / 100` | `quiz_attempt:{id}` | 需要已取得稳定数据库主键 |
| 诊断答对 | `0.78` | `diagnostic:{session}:{question}` | 与现有诊断基线分一致 |
| 诊断答错 | `0.32` | `diagnostic:{session}:{question}` | 与现有诊断基线分一致 |
| 诊断跳过 | 不生成事件 | — | 禁止把未测解释成 0 分 |
| 费曼 | `result.score / 100` | `feynman:{session}:{turn}` | 只接收评估数值，不由文本直接写分 |
| 步骤完成 | `1.0` | `learning_step:{row_id}:{step}` | `done=false` 不生成正向证据 |

幂等策略：`learning_events.event_id` 建唯一约束/唯一索引。重复的完全相同事件直接返回现有状态；同一 `event_id` 携带不同内容时抛出冲突错误，不静默覆盖。迟到事件和同时间事件分别按 `(timestamp, event_id)` 重放，保证结果不依赖投递顺序。

## 3. Shadow 差异

Shadow 对同一 LearningEvent 历史执行两套口径：

- Legacy Mastery：仅处理 diagnostic/quiz，按时间取最后一次能力证据覆盖；confidence 固定采用现有诊断 `0.45`、Quiz `0.85` 口径。
- KnowledgeState：处理全部 Evidence，应用类型权重、时间衰减、对数几率累积和置信度累积。

固定回放样本包含同一用户/知识点的三条历史：诊断答错（0.32）→ 费曼 82 分 → Quiz 76 分。结果如下：

| 指标 | Legacy | KnowledgeState | 差异 |
|---|---:|---:|---:|
| mastery | 0.7600 | 0.8234 | +0.0634 |
| confidence | 0.8500 | 0.8944 | +0.0444 |
| 分布桶 | proficient | mastered | proficient -1 / mastered +1 |

该样本用于验证计算与报告链路，不代表生产总体效果。当前项目未持久化费曼历史回合，诊断也缺少独立的逐题历史表和发生时间，因此不能从现有数据库可靠构造全量真实历史；本阶段不伪造总体样本量或准入结论。

离线回放命令：

```bash
cd backend
python scripts/replay_learning_events.py --user-id u_10001 --knowledge-id ml
```

输出包含节点级 mastery/confidence 差异、均值绝对差和 `unknown/low/learning/proficient/mastered` 分布变化。工具只读取 `LearningEvent`，不写 `Mastery`。

## 4. 风险分析

1. **历史覆盖不完整**：Quiz 和步骤已有持久记录；费曼仅有 TTL 会话，诊断缺少独立逐题事件历史。Shadow 目前更适合新流量旁路采集，不能声称已覆盖全部旧历史。
2. **证据相关性**：连续费曼回合、同一 Quiz 重做并非完全独立，当前累积可能抬高 confidence。后续需加入重复惩罚和会话内聚合。
3. **阈值跨越**：样本从 proficient 跨到 mastered，说明弱/中强证据累积可能改变内部层级。Shadow 阶段禁止据此触发对外 passed 或路径重排。
4. **来源 ID 稳定性**：Quiz/步骤有数据库主键；诊断/费曼必须由调用边界提供稳定 session/turn/question ID，否则无法保证跨进程幂等。
5. **算法版本回放**：事件记录采集时版本；未来升级必须并行重算并保留版本报告，不能覆盖历史事件。
6. **Legacy 时间信息不足**：`Mastery` 是快照且无更新时间，旧快照无法还原严格时序。差异分析应以完整 LearningEvent 历史为准。

## TASK-005-D 建议

- 在不改变线上响应的前提下，将四个既有服务边界旁路写入 LearningEvent，先补齐真实 Shadow 样本；
- 为诊断和费曼生成稳定的 source_id，并持久化必要的发生时间与分数，不保存多余原文；
- 增加重复尝试惩罚、冲突证据降置信和按来源/知识点分层的差异门禁；
- 以至少 7/30 天窗口观察 mastery MAE、confidence 偏移、分布迁移率和跨阈值率；
- 未完成离线校准与人工抽样复核前，继续禁止 KnowledgeState 写回 Mastery 或驱动线上路径。
