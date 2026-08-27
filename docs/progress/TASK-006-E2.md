# TASK-006-E2 LLMClient 内容安全守卫注册边界拆分

## 完成状态

已完成 TASK-006-E 的第二个渐进拆分边界。将 LLMClient 内容安全守卫的方法清单与统一安装逻辑从 `app/core/llm.py` 迁移到职责所属的 `app/core/content_safety.py`；`llm.py` 在类定义结束后只调用安装入口。

TASK-006-E 主任务保持进行中。本轮未修改内容安全词表、判定规则、Provider、Prompt、Mock 生成器、前端页面或其他能力边界，未进入 TASK-006-F。

本阶段新增文件 1 个，符合每阶段新增文件不超过 8 个的约束。

## 边界与兼容性

- 16 个同步生成出口的清单保持不变。
- `tutor_chat_stream` 流式安全守卫保持不变。
- `guarded`、`guarded_stream` 的实现及返回结构保持不变。
- 新增自动断言，确保清单内同步方法及流式方法均带有安全装饰器。
- `LLMClient` 公共方法、统一响应信封、Mock 输出和接口字段均未改变。
- `llm.py` 从 E1 后的 3171 行降至 3137 行。

## 文件清单

新增：

- `docs/progress/TASK-006-E2.md`

修改：

- `backend/app/core/content_safety.py`
- `backend/app/core/llm.py`
- `backend/tests/test_content_safety.py`
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
python -m pytest -q tests/test_content_safety.py tests/test_b7a.py tests/test_b10.py tests/test_workflow_b5a.py
```

结果：语法检查退出码 0；专项测试 `62 passed, 1 warning in 5.45s`，0 failed。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`491 passed, 1 skipped, 1 warning in 174.92s`，0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## 验收结论

- 本轮只迁移内容安全守卫注册这一个能力边界。
- 所有声明的同步与流式生成出口仍经过统一内容安全钝化点。
- 接口、Mock 和安全处置行为保持不变。
- 专项与全量回归均为 0 error。
- TASK-006-E 后续拆分仍须逐边界独立实施、验证和提交。
