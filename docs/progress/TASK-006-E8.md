# TASK-006-E8 工作流 Agent Mock 输出拆分

## 完成状态

已完成 TASK-006-E 的第八个渐进拆分边界。将 LangGraph 工作流中 diagnosis、generation、critic 三类 Agent 的确定性 Mock 输出，以及 critic 强制低分测试钩子，从 `app/core/llm.py` 抽取到 `app/core/llm_workflow_mock.py`。

TASK-006-E 主任务保持进行中。本轮未修改真实 Provider 补全、工作流状态机、Prompt 模板、讲义正文构造、审核阈值、前端页面或其他能力边界，未进入 TASK-006-F。

本阶段新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 边界与兼容性

- diagnosis 继续按目标知识点、画像摘要和掌握度确定性生成薄弱点、摘要与依据。
- 非法或非对象 `masteryStatus` 继续回落为空掌握度，固定后备知识点和输出顺序不变。
- generation 继续使用 `LLMClient._lecture_markdown` 构造正文；新模块只接收回调，不迁移讲义生成职责。
- critic 默认分数、幻觉率、问题列表，以及强制低分时的 0.42/0.18 固定结果保持不变。
- `LLMClient._mock_diagnosis`、`_mock_generation`、`_mock_critic` 的方法签名和调用方式保持不变。
- `app.core.llm.set_force_critic_low` 保留为新模块函数的兼容导入，原有测试和 Agent 调用无需修改。
- `llm.py` 从 E7 后的 2751 行降至 2693 行。

## 文件清单

新增：

- `backend/app/core/llm_workflow_mock.py`
- `backend/tests/test_llm_workflow_mock.py`
- `docs/progress/TASK-006-E8.md`

修改：

- `backend/app/core/llm.py`
- `docs/维护/工作任务清单.md`
- `docs/维护/当前工程状态.md`

未修改前端、OpenAPI 快照和接口文档。工作区原有欢迎页、登录页、侧边栏、PPT、截图及其他文档改动均保留且不纳入提交。

## 启动命令

```powershell
cd backend
$env:LLM_PROVIDER='mock'
uvicorn app.main:app --port 8000
```

## 验证命令与实测结果

语法检查与专项回归：

```powershell
cd backend
python -m compileall -q app tests
python -m pytest -q tests/test_llm_workflow_mock.py tests/test_workflow_b5a.py tests/test_b7a.py tests/test_contract_snapshot.py
```

结果：语法检查退出码 0；专项测试 `72 passed, 1 warning in 12.39s`，0 failed。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`532 passed, 1 skipped, 1 warning in 182.78s`，0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## 验收结论

- 本轮只拆分工作流三类 Agent 的确定性 Mock 输出与测试钩子这一个能力边界。
- 工作流字段、Mock 文案、分数、回退规则、讲义构造入口和兼容方法保持不变。
- 专项与全量回归均为 0 error。
- TASK-006-E 后续拆分仍须逐边界独立实施、验证和提交。
