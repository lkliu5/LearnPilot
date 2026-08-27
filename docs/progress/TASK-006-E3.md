# TASK-006-E3 Mock 辅导决策边界拆分

## 完成状态

已完成 TASK-006-E 的第三个渐进拆分边界。将确定性 Mock 苏格拉底回复链、问题点关键词识别和四类补救资源建议构造从 `app/core/llm.py` 抽取到 `app/core/llm_tutor_mock.py`。

TASK-006-E 主任务保持进行中。本轮未修改真实 Provider Prompt、辅导会话、资源生成实现、内容安全、前端页面或其他能力边界，未进入 TASK-006-F。

本阶段新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 边界与兼容性

- Mock 苏格拉底关键词分支、回复文案、快捷建议及兜底文案保持不变。
- 问题点关键词与未命中回落规则保持不变。
- 补救资源仍按 `diagram → example → video → lecture` 稳定顺序返回。
- 每项建议仍严格包含 `id/type/title/expect` 四个字段。
- `REMEDIAL_TYPES` 继续由 `app.core.llm` 重导出，`tutor_resource` 服务导入路径无需变化。
- 真实模式 `_TUTOR_SYSTEM`、LLM 调用和契约清洗仍保留在 `LLMClient` 编排层。
- `llm.py` 从 E2 后的 3137 行降至 3047 行。

## 文件清单

新增：

- `backend/app/core/llm_tutor_mock.py`
- `backend/tests/test_llm_tutor_mock.py`
- `docs/progress/TASK-006-E3.md`

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
python -m pytest -q tests/test_llm_tutor_mock.py tests/test_b7a.py tests/test_contract_snapshot.py tests/test_tutor_resource.py tests/test_content_safety.py
```

结果：语法检查退出码 0；最终专项测试 `103 passed, 1 warning in 15.89s`，0 failed。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`494 passed, 1 skipped, 1 warning in 176.74s`，0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## 验收结论

- 本轮只拆分 Mock 辅导决策这一个能力边界。
- Mock 回复、补救资源建议、服务导入路径及真实模式行为保持不变。
- 专项与全量回归均为 0 error。
- TASK-006-E 后续拆分仍须逐边界独立实施、验证和提交。
