# TASK-006-E7 画像契约与 Mock 抽取拆分

## 完成状态

已完成 TASK-006-E 的第七个渐进拆分边界。将固定画像维度、三分类、偏好题契约、画像增量清洗和确定性 Mock 关键词抽取，从 `app/core/llm.py` 抽取到 `app/core/llm_portrait.py`。

TASK-006-E 主任务保持进行中。本轮未修改真实 Provider Prompt、对话会话状态机、诊断微测评分、画像持久化、前端页面或其他能力边界，未进入 TASK-006-F。

本阶段新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 边界与兼容性

- 六个画像维度及原有顺序保持不变。
- `ability`、`preference`、`subjective` 三分类及维度归属保持不变。
- 画像来源枚举、非法来源回落、置信度截断和 inferred 置信度 0.6 上限保持不变。
- 仅能力维保留 0–100 `score`；偏好/主观维继续剥离分数。
- Mock 抽取的关键词、优先级、文案、分数、置信度和首轮 manual 上下文补齐规则保持不变。
- `PORTRAIT_DIMENSIONS`、`PORTRAIT_DIM_KINDS`、三类维度键、偏好题，以及 `_PORTRAIT_KEYS`、`_PORTRAIT_LABELS`、`_PREFERENCE_LABELS`、`_sanitize_portrait_updates`、`_mock_extract_portrait` 均在 `app.core.llm` 保留兼容导入。
- `llm.py` 从 E6 后的 2946 行降至 2751 行。

## 文件清单

新增：

- `backend/app/core/llm_portrait.py`
- `backend/tests/test_llm_portrait.py`
- `docs/progress/TASK-006-E7.md`

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
python -m pytest -q tests/test_llm_portrait.py tests/test_dialogue_profile.py tests/test_contract_snapshot.py
```

结果：语法检查退出码 0；专项测试 `62 passed, 1 warning in 13.74s`，0 failed。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`525 passed, 1 skipped, 1 warning in 135.46s`，0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## 验收结论

- 本轮只拆分画像契约与确定性 Mock 抽取这一个能力边界。
- 接口字段、枚举、清洗规则、Mock 输出和 `llm.py` 兼容名称保持不变。
- 专项与全量回归均为 0 error。
- TASK-006-E 后续拆分仍须逐边界独立实施、验证和提交。
