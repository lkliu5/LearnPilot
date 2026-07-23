# Learning-State Shadow 积累报告

> 阶段：TASK-005-D
>
> 模式：Shadow（只写 `learning_events` / `user_knowledge_states` / `learning_event_anomalies`）
>
> 算法版本：`ks-logodds-v1.1-shadow`
>
> 基线提交：`9b57929`

## 1. 接入来源

四类真实业务成功点均通过独立数据库会话 fail-open 旁路接入。旁路异常只写日志或异常审计，不改变原业务事务、响应字段、状态码和 SSE 事件。

| 来源 | 接入成功点 | source_id 稳定规则 | event_type / source_type |
|---|---|---|---|
| Quiz | `QuizAttempt` 提交并取得数据库主键后 | `quiz_attempt:{attempt.id}` | `quiz / quiz_result` |
| Diagnostic | 对话诊断微测单题完成判定后 | `diagnostic:{sessionId}:{questionId}` | `diagnostic / diagnostic` |
| Feynman | JSON/SSE 单轮评估成功后 | `feynman:{sessionId}:turn-{turnNumber}` | `feynman / feynman` |
| Learning Step | 步骤进度行提交后，仅 `done=true` | `learning_step:{row.id}:{step}` | `learning_step / learning_step` |

`event_id = le_ + SHA-256(source_type + ":" + source_id)` 的前 24 位十六进制字符。同一业务来源重复投递时 event_id 恒定；采集层以业务字段判断重复，允许重试发生时间不同但禁止覆盖原 Event。

## 2. Event 统计

TASK-005-D 可复现实测样本（隔离测试库）包含四类真实结构 Event：

| 指标 | 实测值 |
|---|---:|
| 用户数量 | 1 |
| 用户-知识节点数量 | 1 |
| Event 数量 | 4 |
| Quiz / Diagnostic / Feynman / Learning Step | 1 / 1 / 1 / 1 |
| 重复投递测试 | 2 次投递落 1 个 Event，记录 1 个 `duplicate` |
| 冲突测试 | 2 个 Event，记录 1 个 `evidence_conflict` |

当前工作区持久开发库在报告生成时尚未经过新版应用启动，未创建 `learning_events` 表，因此没有可诚实报告的存量真实用户流量。应用下次启动会由 `init_db()` 建表；之后四个成功点会持续累计真实 Shadow 数据。报告不把测试样本冒充生产样本。

## 3. 状态变化分析

四 Event 验收序列：Quiz 0.76 → Diagnostic 0.78 → Feynman 0.82 → Learning Step 1.0。

| 指标 | Legacy | Shadow | 变化 |
|---|---:|---:|---:|
| mastery | 0.780000 | 0.945410 | +0.165410 |
| confidence | 0.450000 | 0.909267 | +0.459267 |
| 分布 | proficient | mastered | 跨 1 个阈值 |

该样本说明多来源累积会显著提高状态值和置信度，不能据单节点样本开放写回。Shadow 写入前后线上 `Mastery` 全表快照完全一致；线上学习路径仍只读取原有 Mastery/业务表。

## 4. 异常情况

1. **重复证据**：同 event_id 且业务字段一致时幂等忽略，不重复计算状态，并追加 `duplicate` 审计。
2. **event_id 载荷冲突**：同 event_id 但用户、节点、类型、来源或分数不同，拒绝覆盖并记 `duplicate_conflict`。
3. **证据冲突**：24 小时窗口内分数方向跨越 0.5 且绝对分差至少 0.40，记录 `evidence_conflict`；只将 Shadow confidence 乘 0.75，mastery 仍按原证据公式计算。
4. **旁路失败**：采集使用独立 Session 并捕获全部异常，返回 `capture_failed` 给内部日志，不向线上 API 传播。
5. **迟到事件**：知识状态继续按 `(timestamp, event_id)` 全量重放，结果不依赖到达顺序。

## 5. 算法校准建议

1. 至少累计 7 天与 30 天两个观察窗口，按来源、知识点、用户活跃层分层报告，不以整体均值替代分层差异。
2. 重点监控 mastery MAE、confidence 偏移、阈值迁移率、冲突率、重复率和 source 覆盖率；跨阈值样本必须人工抽检。
3. 当前 Learning Step 权重虽低，但连续步骤会持续推高 confidence；TASK-005-E 应评估同会话/同日聚合上限。
4. Diagnostic 单题和 Feynman 轮次存在相关性，建议评估来源内去相关、时间窗口衰减与按 session 封顶。
5. 冲突阈值 `24h / 0.40 / 0.75` 属首版工程参数，应基于真实标注样本做网格回放后再冻结。
6. 未完成离线校准、人工抽样与门槛评审前，继续禁止写回线上 Mastery 或驱动学习路径。
