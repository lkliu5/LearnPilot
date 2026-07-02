# 文档学习 → NotebookLM 式三栏体验（升级总结）

会话目标：把「文档学习」升级为 NotebookLM 式三栏体验 —— **左栏来源与概览 · 中栏和文档即问即答 · 右栏生成六类**，
新增**多文件上传 + 多选统一生成**与**和文档对话（严格基于文档、流式、溯源）**，全部复用现有 RAG / 专属向量集合 /
六类生成 / 概览 / 流式问答 / 资源库下载能力，向量库与内置隔离，不改既有接口签名，Mock 兜底全链路可跑。

## 一、改动文件清单

### 后端（改 4 + 新 1）
- `app/services/document_generation.py`（改）：`_retrieve`/`_sources` 重构为**多文档合并检索范围**——各文档在**各自专属集合**检索、内存候选池合并统一重排、来源按各文档标题标注；新增 `resolve_docs` / `retrieve` / `sources_of` / `_merged_title`；六类生成签名改为 `doc_ids: list[str]`，响应加 `docIds`，多篇资源库以主文档 + 合并标题落库。概览仍单篇。
- `app/core/llm.py`（改）：新增 `LLMClient.doc_chat_stream`（严格基于文档、`[n]` 溯源、mock 逐字流式 / deepseek 真实流式）+ `_DOC_CHAT_SYSTEM` + `_mock_doc_answer`（确定性、防幻觉、无检索答"文档中未提及"）。
- `app/schemas/document.py`（改）：六类生成请求基类 `_DocGenBase` 加**可选** `documentIds`（`.doc_ids()` 归一，向后兼容单篇）；新增 `DocChatRequest`。
- `app/api/v1/document.py`（改）：六类路由改传 `body.doc_ids()`；新增 `POST /document/chat`（Accept 头切 SSE / JSON，归属+就绪校验走信封）。
- `app/services/document_chat.py`（**新**）：文档问答服务——会话 TTL 30min（独立池）+ `sse_stream`/`chat`，复用 `document_generation` 检索与来源，`done` 事件携带 `sources` 溯源。

### 前端（改 2 + 新 3）
- `src/pages/DocumentLearning.tsx`（改）：**三栏重排**（来源+概览 / 问答 / 生成）；多选 `checkedIds`（勾选=合并范围）+ 聚焦 `focusedId`（概览目标+主文档）；**概览移至左栏**；生成按 `scopeKey` 归档、多篇传 `documentIds`；中栏挂 `DocumentChat`。
- `src/services/documentLearning.ts`（改）：六类生成加**可选** `documentIds` 透传；多文档 mock 合并（`mergedSentences`/`mergedSources`/`mergedTitle`）；导出 `mockDocAnswer`（离线问答兜底）。
- `src/components/DocumentChat.tsx`（**新**）：中栏问答，复用 `ChatPanel`（`.socratic`）+ `SourceTrace`；逐 delta 渲染、历史保留、每答溯源；切换范围重置会话。
- `src/services/documentChat.ts`（**新**）：`streamDocChat`——真实 SSE（超时/首字节看门狗）+ 离线 mock 逐字兜底，`done` 带回 `sources`。
- `src/components/DocumentChat.css`（**新**）+ `src/pages/DocumentLearning.css`（改）：三栏栅格 + 多选勾选样式 + 概览左栏 + 响应式（≤1180 生成栏下沉、≤860 三栏纵向堆叠）。

## 二、接口增量（`docs/后端接口文档.md`）
- §20.5 增补：六类生成新增**可选** `documentIds`（多篇合并检索范围统一生成，向后兼容单篇）；多篇响应加 `docIds`、来源分篇标注、隔离不建持久化合并集合。
- §20.8 文档概览（AI 速读）：补录既有 `POST /document/generate/overview`（左栏速读、不入资源库）。
- §20.9 和文档对话：新增 `POST /document/chat`（SSE / JSON、严格基于文档、`[n]` 溯源、Mock 兜底）。

## 三、启动与验证命令
```bash
cd backend && uvicorn app.main:app --port 8000     # 无 Key = mock 全链路可跑
cd frontend && npm run dev                          # :3001，/api 代理 :8000
cd backend && pytest -q                             # 全量回归
cd frontend && npx tsc --noEmit                     # 类型检查
```

## 四、验证结果（截图见 `.playwright-mcp/verify-*.png`）
1. **多文件上传 + 多选统一生成**：一次上传 doc-alpha(ZetaVec)+doc-beta(KappaAttn)，勾选 2 篇 → 生成讲义标题「卡帕注意力与泽塔向量收敛定理…」、正文与 4 条来源**同时覆盖两篇**（非只用其一）。✅
2. **中栏文档问答**：就 2 篇提问 → **真实 SSE 逐字流式**、答案严格基于文档、`[1]-[4]` 行内溯源 + 「本回答溯源」列出两篇来源、问答历史保留。✅
3. **左栏概览**：选中文档在左栏展示 AI 速读（是什么/讲了什么/结构/关键点），随聚焦切换。✅
4. **右栏生成 + 资源库下载**：六类可生成、可查看；多篇讲义进「我的资源库」（`doc-beta 等 2 篇文档`）可下载，与内置资源并存。✅
5. **三栏 + 主题 + 响应式**：三栏清晰；`鼠尾草`/`墨纸`（data-theme=ink）主题均正常；≤1180 生成栏下沉、≤860 纵向堆叠（来源→问答→生成）。✅
6. **无回归 + 隔离 + 干净**：`pytest` **244 passed, 1 skipped**；`tsc` 0 错；清载后文档学习 0 console error；文档专属集合与内置 `kb_chunks` 隔离（后端 `test_collection_isolated_from_builtin_kb` + 资源库文档/内置并存）。✅

## 五、红线自检
- 未改内置课程画像 / 诊断 / 路径 / 掌握度与任何既有接口签名：`documentIds` 为**可选追加**、单篇行为不变；新增仅 `POST /document/chat`。
- 向量库隔离：多文档在各自 `doclearn_<id>` 集合检索、仅内存候选池合并，不建持久化合并集合、不碰内置 `kb_chunks`。
- Mock 兜底：`provider=mock`（无 Key）时问答/生成/概览均确定性合成、全链路可跑；前端 `VITE_USE_REAL_API=false` 离线亦可。
- 不做链接 / 网页 / YouTube 来源；问答是「理解文档」，资源生成仍走右栏，二者独立并存。
- 前端仅改数据获取层 `src/services/` 与文档学习页；未动 Zustand store 结构 / 路由 / 其它页面业务逻辑。

> 备注：本会话运行态用的是**真实 DeepSeek**（环境已配 Key），故截图中的问答/概览为真实生成；无 Key 时按 mock 兜底同样跑通。
