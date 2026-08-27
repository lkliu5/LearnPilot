# TASK-006-E4 练习题自洽审核边界拆分

## 完成状态

已完成 TASK-006-E 的第四个渐进拆分边界。将结构化练习题的题型、题干、选项、正确答案和解析自洽性审核从 `app/core/llm.py` 抽取到 `app/core/llm_practice.py`。

TASK-006-E 主任务保持进行中。本轮未修改练习生成、学生答案评分、Provider、Prompt、Mock 题库、前端页面或其他能力边界，未进入 TASK-006-F。

本阶段新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 边界与兼容性

- 客观题型仍限定为 `single/multiple/boolean`。
- 题干非空、至少两个选项、选项 ID 不重复等规则保持不变。
- 单值正确答案必须存在于选项中；多选答案必须非空且全部存在于选项中。
- 解析仍要求非空，问题清单顺序和错误文案保持稳定。
- `audit_practice` 继续由 `app.core.llm` 重导出，文档生成、测验服务及既有测试无需改导入路径。
- `SHORT_ANSWER_TYPE` 与简答题评分不属于本边界，仍留在 LLM 编排层。
- `llm.py` 从 E3 后的 3047 行降至 3017 行。

## 文件清单

新增：

- `backend/app/core/llm_practice.py`
- `backend/tests/test_llm_practice.py`
- `docs/progress/TASK-006-E4.md`

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
python -m compileall -q app
python -m pytest -q tests/test_llm_practice.py tests/test_document_learning.py tests/test_contract_snapshot.py tests/test_b7a.py
```

结果：语法检查退出码 0；专项测试 `83 passed, 1 warning in 126.78s`，0 failed。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`502 passed, 1 skipped, 1 warning in 150.95s`，0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## 验收结论

- 本轮只拆分练习题自洽审核这一个能力边界。
- 审核规则、错误文案、公共导入路径及上下游行为保持不变。
- 专项与全量回归均为 0 error。
- TASK-006-E 后续拆分仍须逐边界独立实施、验证和提交。
