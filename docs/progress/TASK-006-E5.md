# TASK-006-E5 确定性文档接地边界拆分

## 完成状态

已完成 TASK-006-E 的第五个渐进拆分边界。将文档检索片段的确定性要点抽取，以及严格基于这些要点生成带 `[n]` 引用的 Mock 文档回答，从 `app/core/llm.py` 抽取到 `app/core/llm_document_mock.py`。

TASK-006-E 主任务保持进行中。本轮未修改真实文档问答 Prompt、RAG 检索、向量库、Provider、文档生成服务、前端页面或其他能力边界，未进入 TASK-006-F。

本阶段新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 边界与兼容性

- 要点句仍按原文顺序抽取，过滤短句、去重、单句截断至 120 字并遵守 `max_n`。
- Mock 回答仍最多列出 3 个要点，按 `[1]`、`[2]`、`[3]` 标注来源。
- 无有效上下文时继续明确返回“未提及相关内容”，禁止文档外推测。
- `_doc_key_sentences` 与 `_mock_doc_answer` 继续由 `app.core.llm` 提供兼容别名；文档生成服务无需改导入路径。
- 真实模式 `_DOC_CHAT_SYSTEM` 和 LLM 调用仍保留在编排层。
- `llm.py` 从 E4 后的 3017 行降至 2979 行。

## 文件清单

新增：

- `backend/app/core/llm_document_mock.py`
- `backend/tests/test_llm_document_mock.py`
- `docs/progress/TASK-006-E5.md`

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
python -m pytest -q tests/test_llm_document_mock.py tests/test_document_learning.py tests/test_contract_snapshot.py
```

最终结果：语法检查退出码 0；专项测试 `61 passed, 1 warning in 49.69s`，0 failed。

专项首次运行时，既有多文档用例遇到 Chroma 测试集合读取失败并降级内存库，造成检索选择波动；该用例隔离复跑 `1 passed`，随后完整专项与全量测试均通过，确认不是本次纯函数迁移回归。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`507 passed, 1 skipped, 1 warning in 102.05s`，0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## 验收结论

- 本轮只拆分确定性文档接地这一个能力边界。
- 要点抽取、引用格式、fail-closed 文案和旧导入路径保持不变。
- 专项与全量回归最终均为 0 error。
- TASK-006-E 后续拆分仍须逐边界独立实施、验证和提交。
