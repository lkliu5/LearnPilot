# TASK-006-E1 LLM 输出解析与 Mermaid 清洗边界拆分

## 完成状态

已完成 TASK-006-E 的第一个渐进拆分边界。将 LLM 自由文本 JSON 提取、Markdown 围栏剥离和 Mermaid 首行图型校验从 `app/core/llm.py` 抽取到独立模块；`llm.py` 保留原私有名称的导入别名，既有内部调用和测试访问保持兼容。

TASK-006-E 主任务保持进行中。本轮未拆 Provider、Prompt、Mock 生成器、确定性图解模板或前端超大页面，避免一次跨越多个能力边界；未进入 TASK-006-F。

本阶段新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 边界与兼容性

- 新模块只处理模型输出，不负责 Provider 调用、Prompt 构造或业务兜底。
- JSON 提取仍先解析完整文本，再解析首个 `{` 到末个 `}` 的兼容块，失败返回 `None`。
- Markdown 围栏剥离行为不变。
- Mermaid 支持图型白名单及异常文案不变，继续抛统一 `LLMGenerationError`。
- `LLMClient`、`get_llm()`、统一响应信封、Mock 输出、接口字段与枚举均未改变。
- `llm.py` 从 3213 行降至 3171 行；本轮只迁移一个内聚纯函数边界。

## 文件清单

新增：

- `backend/app/core/llm_output.py`
- `backend/tests/test_llm_output.py`
- `docs/progress/TASK-006-E1.md`

修改：

- `backend/app/core/llm.py`
- `docs/维护/工作任务清单.md`
- `docs/维护/当前工程状态.md`

未修改前端、OpenAPI 快照或接口文档，因为本轮没有契约变化。工作区原有欢迎页、登录页、侧边栏、PPT、截图和其他文档改动均保留且不纳入提交。

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
python -m pytest -q tests/test_llm_output.py tests/test_model_registry.py tests/test_b7a.py tests/test_contract_snapshot.py
```

结果：语法检查退出码 0；专项测试 `80 passed, 1 warning in 19.12s`，0 failed。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`490 passed, 1 skipped, 1 warning in 195.54s`，0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## 验收结论

- 本轮只拆分一个能力边界。
- 既有接口、异常类型和 Mock 行为保持不变。
- 专项与全量回归均为 0 error。
- TASK-006-E 后续拆分仍需逐边界独立实施、验证和提交。
