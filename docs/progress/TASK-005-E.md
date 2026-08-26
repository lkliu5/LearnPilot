# TASK-005-E Learning-State Shadow 7/30 天观测与校准门槛

## 完成范围

- 新增 7/30 天窗口观测、来源/节点/活跃度分层与窗口漂移；
- 新增 session 证据聚合上限候选和冲突窗口/分差/置信因子离线网格回放；
- 新增跨阈值人工抽样清单；
- 建立最小样本、来源覆盖、误差、迁移、异常率和人工复核的 fail-closed 门槛；
- 未修改 Agent、Workflow、RAG、前端、接口契约、线上 Mastery 或学习路径。

## 文件清单

### 新增（5 个）

- `backend/app/services/knowledge_state_calibration.py`
- `backend/scripts/evaluate_knowledge_state_calibration.py`
- `backend/tests/test_knowledge_state_calibration.py`
- `docs/Learning-State Shadow校准门槛报告.md`
- `docs/progress/TASK-005-E.md`

### 修改

- `backend/app/services/knowledge_state.py`：内部更新函数接受可选离线权重，冲突判断接受可选候选参数；默认值与线上 v1.1 完全一致。
- `docs/维护/当前工程状态.md`：同步知识状态 Shadow 当前完成度、验证结果与后续工作。

本阶段新增文件 5 个，符合每阶段新增文件不超过 8 个的约束。

## 运行命令

```powershell
cd backend
python scripts/evaluate_knowledge_state_calibration.py
python scripts/evaluate_knowledge_state_calibration.py --as-of 2026-08-26T08:00:00+00:00
```

工具只读学习事件和异常审计表，输出 JSON 到标准输出，不修改线上业务表。

## 验证命令与实测结果

定向测试：

```powershell
python -m pytest -q tests/test_knowledge_state.py tests/test_learning_evidence_shadow.py tests/test_learning_event_sidecar.py tests/test_knowledge_state_calibration.py --basetemp=.pytest_task005_e_focus
```

```text
14 passed in 2.40s
```

全量后端回归：

```powershell
python -m pytest -q --basetemp=.pytest_task005_e_full
```

```text
470 passed, 1 skipped, 1 warning in 164.66s (0:02:44)
```

0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

开发库观测实测：

```text
7d:  0 events / 0 users / 0 nodes
30d: 0 events / 0 users / 0 nodes
admission: BLOCK
```

## 结论

离线观测、参数对比和准入门槛已经工程化，但当前没有足量真实连续 Shadow 数据，不能宣称完成算法校准。门槛按设计阻断写回；线上 `Mastery`、路径与 API 行为保持不变。

## 下一阶段建议

下一阶段只做真实 7/30 天数据积累与人工标注。达到 200 Event、20 用户、50 可比节点和四来源覆盖后，复跑本工具并完成跨阈值人工评审；未全部通过前不进入写回或 KAP 局部重规划。
