# B4-a — 管理端骨架 + 知识库管理页 · 完成总结

> 阶段：B4 前半（B4-a）｜状态：✅ 完成（0 报错）｜日期：2026-06-11
> 范围：登录角色分流 + 侧边栏「管理」分组（仅 admin）+ 知识库管理页（对接 B3 四件套）
> + Prompt 管理 / 指标看板占位路由。Prompt 编辑与三 gauge 看板在 B4-b 实装。

## 1. 交付内容

### 角色分流与管理路由守卫（`App.tsx`）

- `PageType` 扩展 `admin-kb / admin-prompts / admin-metrics` 三页。
- 登录后读取 `getUser().role`（接口文档 15.1）：`admin` → 默认进知识库管理页；
  `learner`（或 mock 模式无登录态）→ 原 dashboard 流程，行为与改前一致。
- **管理路由守卫**：`#/admin/kb|prompts|metrics` hash 深链 ↔ 页面双向映射；
  learner 在应用内直接敲管理 hash（或任何方式使 currentPage 落到管理页）一律拦截回首页，
  并清除管理 hash；渲染层再做一次双保险（非 admin 渲染管理页时强制返回 Dashboard）。
  整页刷新场景天然回到 landing→login 入口，无越权窗口。

### 侧边栏「管理」分组（`Sidebar.tsx`，仅 admin 渲染）

- 新增 `isAdmin` prop：admin 登录时在「总览与工具」下方渲染「管理」分组三项
  （知识库管理 / Prompt管理 / 指标看板），沿用既有渐变填充图标语言与 stagger 入场；
  learner 登录**不渲染**该分组（DOM 中不存在，非 CSS 隐藏）。
- 用户卡随登录态显示 `displayName`（admin → 管理员 · 系统运营）；learner 回退值与原硬编码
  文案逐字一致，learner 侧视觉零变化。

### 知识库管理页（`pages/admin/AdminKB.tsx`，对接接口文档 14.1–14.4）

| 功能 | 实现 |
|---|---|
| 文档列表 | 玻璃卡 + 状态徽章（复用全局 `agent-status` 视觉）；存在 `pending/indexing` 文档时每 2s 轮询列表，全部终态自动停止 |
| 上传 | 拖拽或点选 `pdf/md/txt`，multipart 提交（`files` + 可选 `category/tags`），上传后列表立即刷新并进入轮询 |
| 删除 | 玻璃确认弹层（Framer 入退场）→ `DELETE` → toast 反馈 `removedChunks`；当前检索结果中该文档命中同步移除 |
| 检索测试 | query → `POST search-test`：结果卡含 rerank 分数条（0-1）+ `vectorScore`/`bm25Score` 双分参考 + `sourceLocation` 来源徽章；`rerankerUsed=false` 时显示「降级 · 仅 RRF」琥珀徽章。视觉复用 SourceTrace 语言（盾牌头 + 分数条 + mono 字体） |

> 状态徽章按接口文档 14.1 文档状态机 `pending/indexing/indexed/failed`
> （任务状态机的 `succeeded` 对应文档侧的 `indexed`，验收口径一致）。

- Prompt 管理 / 指标看板：占位页（`AdminPlaceholder.tsx`），标注 B4-b 交付与对应接口（14.5/14.6）。
- mock 模式（未设 `VITE_USE_REAL_API=true`）打开管理页显示联调提示条，不发请求、无控制台报错。

### 数据获取层（`services/admin.ts`）

走既有 `api.ts` 信封封装（解 `{code,message,data,traceId}`、自动带 token、非 0 抛 `ApiError`）：
`listKbDocuments / uploadKbDocuments / deleteKbDocument / kbSearchTest`，
类型严格对齐接口文档第 14 章字段名。

## 2. 文件清单

新增 4 个（≤8 上限）：

| 文件 | 说明 |
|---|---|
| `frontend/src/services/admin.ts` | 管理端 KB 四件套数据获取层 + 类型 |
| `frontend/src/pages/admin/AdminKB.tsx` | 知识库管理页（列表/上传/删除/检索测试） |
| `frontend/src/pages/admin/AdminPlaceholder.tsx` | Prompt 管理 / 指标看板占位页 |
| `frontend/src/pages/admin/admin.css` | 管理端样式（全部引用 globals.css 设计令牌） |

**`frontend/src` 既有文件改动（单独列出，按 CLAUDE.md 要求）**：

| 文件 | 改动 | learner 侧影响 |
|---|---|---|
| `frontend/src/App.tsx` | PageType 扩展 3 个管理页；登录角色分流；管理 hash 守卫；渲染管理页 | 无：learner 登录走原 dashboard 路径，页面切换逻辑不变 |
| `frontend/src/components/Sidebar.tsx` | `isAdmin` prop + 管理分组（3 图标 + 3 菜单项）；用户卡读取登录 displayName（回退值与原文案一致） | 无：learner 不渲染管理分组，其余渲染逐字不变 |

后端零改动；learner 六页业务逻辑、Zustand store、既有路由均未触碰。

## 3. 启动 / 验证命令

```bash
# 后端
cd backend && uvicorn app.main:app --port 8000

# 前端（联调模式）
cd frontend && VITE_USE_REAL_API=true npm run dev    # Windows: $env:VITE_USE_REAL_API='true'; npm run dev

# 类型检查 / 构建
cd frontend && npx tsc --noEmit && npm run build
```

种子账号：`admin / admin123`、`learner_001 / 123456`。

## 4. 验证实测（0 报错）

### ① tsc / 构建

```
$ npx tsc --noEmit        → 无输出（0 错误）
$ npm run build           → ✓ 4595 modules transformed, ✓ built in 48.19s
                            （chunk>500kB 提示为既有现象，非本阶段引入）
```

Vite dev server 对 6 个新增/改动模块按需编译全部 200，无编译错误。

### ② 后端联调闭环（curl 实测，对应页面行为逐一对齐）

```
[admin 登录] role=admin displayName=管理员 ✅（App 分流进管理端视图）

[learner 访问 KB] GET /admin/kb/documents
  → {"code":1003,"message":"无权限：需要管理员角色"} <HTTP 403> ✅

[admin 上传 b4a_test.md] → taskId=t_7bdcae6f8e12, doc_004 status=pending
[列表轮询（页面 2s 间隔同口径）]
  poll#1–#11 → indexing, chunks=0
  poll#12    → indexed,  chunks=1          ✅ 徽章 待入库→入库中→已入库

[search-test「卷积神经网络如何提取局部特征」topK=5]
  rerankerUsed=true
  doc_004#0  score=0.7310 vec=0.7650 bm25=24.80 | B4a 验收文档 / 第一章 卷积神经网络 / 段落 1   ← 新文档 top1
  doc_001#1  score=0.5162 vec=0.5795 bm25=4.07  | …/第一章 神经元与前向传播 / 段落 1
  …                                          ✅ 分数条 + 双分 + 来源徽章数据齐全

[DELETE doc_004]   → {"deleted":true,"removedChunks":1} ✅（页面 toast 反馈口径）
[DELETE doc_NOPE]  → {"code":1004,"message":"文档不存在"} <HTTP 404>
[删除后再检索]      → results=5，doc_004 不再命中 ✅ 列表与检索同步消失
```

### ③ 角色拦截（代码级保证 + 实测口径）

- learner 登录：`isAdmin=false` → Sidebar 管理分组不渲染（条件渲染，DOM 不存在）。
- learner 应用内敲 `#/admin/kb`：hashchange 守卫清除 hash 并 `setCurrentPage('dashboard')`；
  渲染层双保险兜底。admin 同 hash 正常进入对应管理页。
- 浏览器 UI 走查（badge 动效/拖拽上传/弹层）依赖人工，本机无浏览器自动化工具；
  以上行为均有 curl 同口径数据验证 + tsc/build 0 报错背书。

## 5. 边界确认 / 给 B4-b 的约定

- 列表轮询采用「整表轮询」而非逐 task 轮询：与 14.2 契约一致，多文档并发上传时一个定时器覆盖全部。
- `admin.css` 为管理端共享样式（AdminKB + 占位页），B4-b 的 Prompt 编辑/指标 gauge 直接续用
  `akb__` 前缀或新增前缀均可，不再新建设计令牌。
- B4-b 范围：Prompt 管理（GET/PUT `/admin/prompts/{agentId}`，热更新 + version 自增）
  + 指标看板（GET `/admin/metrics`，三 gauge 复用 CountUp）+ 后端两个新接口（14.5/14.6）。
