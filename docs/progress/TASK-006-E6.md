# TASK-006-E6 通用确定性评分原语拆分

## 完成状态

已完成 TASK-006-E 的第六个渐进拆分边界。将字符二元组、参考要点覆盖率、来源可信度启发式和 0–100 分数截断，从 `app/core/llm.py` 抽取到 `app/core/llm_scoring.py`。

TASK-006-E 主任务保持进行中。本轮未修改简答题评分阈值、资源排序公式、Provider、Prompt、候选资源契约、前端页面或其他能力边界，未进入 TASK-006-F。

本阶段新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 边界与兼容性

- 字符二元组继续先去除空白并转小写。
- 要点覆盖率仍为“参考要点二元组与作答二元组交集 / 参考要点二元组数”，空要点返回 0。
- 来源可信度仍按 97、95、93、90 四档关键词匹配，未命中返回 82。
- 分数仍截断到 0–100，非法输入返回调用方默认值。
- `_char_bigrams`、`_point_coverage`、`_credibility_of`、`_clamp_score` 在 `app.core.llm` 中保留兼容别名。
- 简答评分与资源聚合继续使用原名称和原算法。
- `llm.py` 从 E5 后的 2979 行降至 2946 行。

## 文件清单

新增：

- `backend/app/core/llm_scoring.py`
- `backend/tests/test_llm_scoring.py`
- `docs/progress/TASK-006-E6.md`

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
python -m pytest -q tests/test_llm_scoring.py tests/test_b6.py tests/test_resource_search.py tests/test_contract_snapshot.py
```

结果：语法检查退出码 0；专项测试 `81 passed, 1 warning in 15.64s`，0 failed。

全量回归：

```powershell
cd backend
python -m pytest -q
```

结果：`520 passed, 1 skipped, 1 warning in 148.75s`，0 failed、0 errors。唯一 warning 为既有 Starlette/httpx 弃用提示。

## 验收结论

- 本轮只拆分通用确定性评分原语这一个能力边界。
- 所有阈值、公式、默认值及 `llm.py` 兼容名称保持不变。
- 专项与全量回归均为 0 error。
- TASK-006-E 后续拆分仍须逐边界独立实施、验证和提交。
