# TASK-005-C 学习证据适配与知识状态 Shadow 计算

## 完成范围

- 建立 Quiz、诊断、费曼讲解、学习步骤完成四类 Learning Evidence Adapter；
- 增强 LearningEvent 协议，增加 `event_id/source_type/source_id/algorithm_version`；
- 增加数据库兼容迁移、`event_id` 唯一索引和幂等/冲突校验；
- 增加按 `(timestamp, event_id)` 的确定性历史回放；
- 增加 Legacy Mastery vs KnowledgeState Shadow 差异与分布报告；
- 未修改 Agent、Workflow、RAG、前端或线上 API 返回，未回写现有 Mastery。

## 修改文件

### 新增

- `backend/app/services/learning_evidence.py`
- `backend/app/services/knowledge_state_shadow.py`
- `backend/scripts/replay_learning_events.py`
- `backend/tests/test_learning_evidence_shadow.py`
- `docs/Learning-State Shadow评估报告.md`
- `docs/progress/TASK-005-C.md`

### 修改

- `backend/app/schemas/knowledge_state.py`
- `backend/app/models/entities.py`
- `backend/app/services/knowledge_state.py`
- `backend/app/core/init_db.py`
- `backend/tests/test_knowledge_state.py`

本阶段新增文件 6 个，符合每阶段新文件不超过 8 个的约束。

## 启动/工具命令

```bash
cd backend
uvicorn app.main:app --reload --port 8000
python scripts/replay_learning_events.py --user-id u_10001 --knowledge-id ml
```

## 验证命令与实测结果

定向测试：

```bash
python -m pytest -q tests/test_knowledge_state.py tests/test_learning_evidence_shadow.py
```

结果：

```text
........                                                                 [100%]
8 passed in 2.60s
```

全量测试（Windows 系统临时目录无权限，显式使用工作区 basetemp）：

```bash
python -m pytest -q --basetemp F:\软件杯\backend\.pytest_task005_c_full
```

结果：

```text
464 passed, 1 skipped, 1 warning in 119.38s (0:01:59)
```

唯一 warning 为既有 Starlette/httpx 弃用提示；测试 0 failed、0 errors。

## Shadow 基准结果

固定三事件回放样本：diagnostic 0.32 → feynman 0.82 → quiz 0.76。

- Legacy mastery：0.7600；KnowledgeState：0.8234；差异 +0.0634；
- Legacy confidence：0.8500；KnowledgeState：0.8944；差异 +0.0444；
- 分布：proficient → mastered；
- Shadow 计算前后 `Mastery` 快照完全一致。

## TASK-005-D 建议

下一阶段只做旁路接线和真实样本观测：将四类 Adapter 接到既有服务成功提交点，稳定生成 source_id，累计 7/30 天 Shadow 指标；在校准、重复证据惩罚和跨阈值人工复核完成前，不允许写回 Mastery 或改变线上路径结果。
