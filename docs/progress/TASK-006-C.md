# TASK-006-C 生成结果溯源元数据统一

## 完成状态

已完成。结构化 AI 生成结果统一追加 `generationMeta`，不改变统一响应信封及既有业务字段；Mock、真实内置模型、自建模型、缓存、确定性生成和两类降级路径均可区分。

本阶段严格停在 TASK-006-C，未继续下一任务；未修改 `frontend/src`。新增文件 3 个，符合每阶段新增文件不超过 8 个的约束。

## 契约

```json
{
  "provider": "mock",
  "model": "mock",
  "source": "builtin|custom|mock|cache|fallback|deterministic",
  "degraded": false,
  "fallbackReason": null
}
```

- JSON 对象结果：写入 `data.generationMeta`。
- JSON 数组结果（`POST /reinforce`）：写入每个生成项的 `generationMeta`，保持数组契约。
- SSE：写入最终 `event: done` 的 data 对象。
- 缓存命中固定为 `provider=cache, model=persisted-artifact, source=cache`，不猜测旧产物的原始模型。
- 自建/ModelScope 调用失败并转 DeepSeek：记录实际 DeepSeek，`source=fallback, degraded=true, fallbackReason=provider_unavailable`。
- LLM 失败转内部模板：`source=fallback, degraded=true, fallbackReason=deterministic_fallback`；异常原文和密钥不进入元数据。
- OpenAPI 以 `x-zhixue-generation-meta: true` 标记当前 25 个结构化生成操作，并新增 `GenerationMeta` Schema。

任务受理响应、普通查询及二进制 TTS 不冒充生成产物，因此不添加该字段。无材料导致 `data=null` 时没有可承载的生成结果，也不改变既有 null 契约。

## 文件清单

新增：

- `backend/app/core/generation_provenance.py`
- `backend/tests/test_generation_provenance.py`
- `docs/progress/TASK-006-C.md`

修改：

- API 接入：`backend/app/api/v1/{dashboard,document,job_market,learning,profile,quiz,resource}.py`
- 模型执行追踪：`backend/app/core/{llm,llm_transport}.py`
- OpenAPI：`backend/app/core/openapi_contract.py`、`backend/contracts/openapi-v1.snapshot.json`
- SSE/缓存/确定性来源：`backend/app/services/{document_chat,document_generation,learning_flow,profile_dialogue,resource,tutor}.py`
- 契约回归：`backend/tests/test_{b7a,c2_learning_flow,contract_snapshot,dialogue_profile,learning_eval,openapi_snapshot,resource_artifact,resource_search,tutor_resource}.py`
- 权威接口文档：`docs/后端接口文档.md`（V1.5）

## 启动命令

```powershell
cd backend
$env:LLM_PROVIDER='mock'
uvicorn app.main:app --port 8000
```

## 验证命令与实测结果

语法：

```powershell
python -m compileall -q app
```

结果：退出码 0。

专项契约：

```powershell
python -m pytest -q tests/test_contract_snapshot.py tests/test_generation_provenance.py tests/test_openapi_snapshot.py
```

结果：`51 passed, 1 warning in 9.90s`。

全量回归：

```powershell
python -m pytest -q
```

最终结果：`480 passed, 1 skipped, 1 warning in 131.99s`，0 failed。warning 为既有 Starlette/httpx 弃用提示。

真实服务 curl（临时端口 8765，Mock 模式）：

```text
GET /api/v1/resource/mindmap/nn
HTTP 200
{"code":0,"message":"ok","data":{"markdown":"...","generationMeta":{"provider":"internal","model":"deterministic","source":"deterministic","degraded":false,"fallbackReason":null}},"traceId":"f06563d897ba"}

POST /api/v1/resource/tutor/chat
Accept: text/event-stream
...
event: done
data: {"sessionId":"s_03522b2d22","suggestions":[...],"generationMeta":{"provider":"mock","model":"mock","source":"mock","degraded":false,"fallbackReason":null}}
```

验证后已关闭临时服务，`PORT_8765_CLOSED`。

## 验收结论

- 统一信封仍严格为 `{code,message,data,traceId}`。
- 无 API Key 的 Mock 全链路可运行。
- 生成元数据反映实际执行路径，缓存与降级不伪装成当前配置模型。
- JSON、数组产物与 SSE `done` 均有明确兼容策略。
- OpenAPI 快照当前，历史业务契约和前端均无回归。
