# TASK-006-E9 确定性 Mermaid 图解边界拆分

## 完成状态

已完成 TASK-006-E 的第九个渐进拆分边界。将 19 个固定 Mermaid 知识图解模板，以及未收录知识点的确定性通用图解生成器，从 `app/core/llm.py` 抽取到 `app/core/llm_diagram.py`。

TASK-006-E 主任务保持进行中。本轮未修改 `LLMClient.generate_diagram` 编排、真实 Provider Prompt、Mermaid 输出清洗、资源接口、前端页面或其他能力边界，未进入 TASK-006-F。

本阶段新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 边界与兼容性

- `nn/ml/dl/cnn/transformer/finetune` 六个核心模板和 `GEN-1`～`GEN-13` 十三个生成式模型模板逐字保留。
- 模板首行图型、节点、连线、公式、中文文案及末尾换行保持不变。
- 通用生成器继续按“分类/类型/组成”等关键词选择 `graph TD`，否则选择带反馈回路的 `flowchart LR`。
- GEN 板块继续固定模板优先；其他知识点继续保持 Mock 使用模板、真实生成失败回落模板的原有策略。
- `app.core.llm._DIAGRAM_TEMPLATES` 与 `_generic_diagram` 保留为新模块对象的兼容别名，既有测试和调用无需修改。
- 迁移前后执行逐行机械一致性校验，315 行模板与生成逻辑除公开名称外完全一致。
- `llm.py` 从 E8 后的 2693 行降至 2382 行。

## 文件清单

新增：

- `backend/app/core/llm_diagram.py`
- `backend/tests/test_llm_diagram.py`
- `docs/progress/TASK-006-E9.md`

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
python -m pytest -q tests/test_llm_diagram.py tests/test_b7a.py tests/test_model_registry.py tests/test_contract_snapshot.py tests/test_tutor_resource.py
```

结果：语法检查退出码 0；专项测试 `97 passed, 1 warning in 17.46s`，0 failed。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`553 passed, 1 skipped, 1 warning in 135.49s`，0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## 验收结论

- 本轮只拆分固定 Mermaid 模板与通用确定性图解生成这一个能力边界。
- 图解模板、生成规则、Provider 回落策略、接口返回和 `llm.py` 兼容名称保持不变。
- 专项与全量回归均为 0 error。
- TASK-006-E 后续拆分仍须逐边界独立实施、验证和提交。
