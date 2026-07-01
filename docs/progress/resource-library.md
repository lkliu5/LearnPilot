# 我的资源库（生成历史）— 完成总结

> 从零新建「我的资源库」：用户生成历史埋点 + 分页查询接口 + 前端资产视图（查看/下载）。
> 契约权威：新增接口文档第 19 章；未改任何既有接口签名（全部「新增追加」）。

## 一、数据层

新增 ORM 表 `GenerationLog`（`backend/app/models/entities.py`）：

| 列 | 类型 | 说明 |
|---|---|---|
| id | int PK | 自增 |
| user_id | str(64) index | 归属用户（token 的 sub）|
| kp_id | str(32) index | 知识点 |
| kind | str(16) | 归一化基类：lecture/video/diagram/mindmap/code |
| difficulty | str(16) | 图解/导图/代码无难度 → "" |
| title | str(256) | 展示标题（知识点名 · 形态[（难度）]）|
| resource_ref | str(512) | 定位引用 `kind:kp_id:difficulty` |
| created_at | datetime index | 最近生成时间 |

- 唯一约束 `(user_id, kp_id, kind, difficulty)` → **upsert 去重**：重复生成/再取仅刷新 `created_at`，避免历史噪声。
- **无外键耦合**（与 `QuizAttempt`/`LearningNote` 同风格），不改既有表结构。
- 与无用户归属的全局缓存 `ResourceCache` **区分**：后者按 `(kp,difficulty,kind)` 供全体复用，本表记「谁生成过什么」。
- 建表由 `Base.metadata.create_all` 自动完成（全新表，无需 ALTER 迁移）；`init_db.py` 追加 import 注册。

## 二、埋点（不改既有生成逻辑，追加式旁路）

- **后端路由旁路埋点**（`backend/app/api/v1/resource.py`）：`/resource/lecture`、`/resource/video`、`/resource/diagram/{kp}` 生成成功后调 `generation_log.record(...)`。生成 service 逻辑**逐字未动**。
- **前端补埋**（`frontend/src/pages/LearningResource.tsx` 的 `generateOne`）：思维导图/代码无独立后端生成接口 → 调 `POST /resource/history/log`（`logResourceGeneration`）。mock 模式 no-op，失败仅告警。
- `record()` 全程 try/except：**埋点失败绝不打断生成主链路**；kind 归一化剥离 `@provider`/`#tier` 后缀，非五类白名单静默忽略。

## 三、接口（新增，套统一信封）

新增路由 `backend/app/api/v1/resource_history.py`（注册于 `main.py`）：

- `GET  /api/v1/resource/history` — 按用户分页；filter：`kind`/`kpId`/`startTime`/`endTime`；回 `{items[],total,page,pageSize}`，`items[]` 含 `kpName`。
- `POST /api/v1/resource/history/log` — 追加埋点（幂等 upsert），供前端补埋 mindmap/code。

服务实现：`backend/app/services/generation_log.py`（`record` / `list_history`；`createdAt` 显式标注 UTC，避免前端时区误读）。
接口文档增量：`docs/后端接口文档.md` 新增「## 19. 我的资源库·生成历史 Resource Library」（19.1 / 19.2）。

## 四、前端

- 入口：左侧「总览与工具」组新增「我的资源库」（`Sidebar.tsx` 图标 `myResources` + `toolItems`）与 `PageType 'my-resources'` + 路由（`App.tsx`）。
- 页面 `pages/MyResourceLibrary.tsx` + `.css`：横向资产网格（形态/知识点/难度/时间），类型 chips + 知识点下拉 + 时间快捷筛选 + 形态小结 + 空态（区分「库为空」/「筛选无结果」）+ 加载/错误态；套设计令牌，深浅主题跟随。
- 服务 `services/resourceHistory.ts`：真实（`GET /resource/history`）/ mock（本地合成 9 条示例，客户端筛选）双模式 + `logResourceGeneration`。
- 预览 `components/ResourceLibraryPreview.tsx`：**在资源库内查看 + 下载**，复用既有多模态组件与导出：
  - 讲义 → `MarkdownRenderer` + `exportLectureMarkdown`/`exportLectureToPdf`（md/pdf）；
  - 视频 → `VideoLecture`（服务端渲染 mp4 就绪即可下载，内置降级实时播放）；
  - 图解/导图 → `MermaidDiagram`/`MindMap`（内置 SVG/PNG）；
  - 代码 → `CodeSandbox`（内置代码文件下载）；
  - 另有「在学习页打开」跳转（`setResourceNav` + 落点 Tab）。
- `VideoLecture.tsx`：新增**可选** `kpId` prop（默认 `getResourceKpId()`，原行为不回归），使资源库预览按记录 kp 取正确视频。

## 五、验证结果

- 后端全量：`pytest -q` → **229 passed, 1 skipped**（含新增 `tests/test_resource_history.py` 7 例：生成→列出、log 幂等、kind/kpId/时间过滤、用户隔离、非法 kind 忽略、鉴权）。
- 前端类型：`npx tsc --noEmit` → **0 error**。
- 真机联调（真实后端 :8000 + 前端 :3001，`VITE_USE_REAL_API=true`）：
  1. 登录 learner_001 → 生成讲义/视频/图解/代码 → 资源库按时间倒序列出 4 条（属当前用户），形态小结正确；
  2. 类型/知识点/时间筛选可用；筛选无结果 → 友好空态；
  3. 逐类型在库内查看 + 下载：讲义（md/pdf）、图解（svg/png，真实 Mermaid 渲染）、视频（服务端 mp4 + 下载，旁白随 CNN 知识点正确生成，验证 `kpId` prop）；
  4. 墨纸/鼠尾草主题切换渲染正常；全流程 **0 console error**。
- Mock 模式（`VITE_USE_REAL_API=false`）：资源库展示 9 条示例记录（跨知识点/形态/难度/时间），0 console error。

## 六、启动 / 验证命令

```bash
# 后端
cd backend && uvicorn app.main:app --port 8000
cd backend && pytest -q                       # 229 passed

# 前端（联调）
cd frontend && npm run dev                     # VITE_USE_REAL_API=true → :3001
cd frontend && npx tsc --noEmit                # 0 error

# 接口自测
curl -s "http://localhost:8000/api/v1/resource/history?pageSize=50" -H "Authorization: Bearer <token>"
```

## 七、红线自检

- ✅ 未改任何既有接口路径/字段/枚举；仅新增 19.1/19.2 + 前端 `VideoLecture` 可选 prop（additive）。
- ✅ 未改既有生成逻辑（services/resource.py 未动），埋点为旁路追加；埋点失败不阻断生成。
- ✅ 统一响应信封 `{code,message,data,traceId}`；`GenerationLog` 无外键耦合、user 隔离。
- ✅ Mock-first：无 API Key 全链路可跑；前端 mock 模式有示例记录。
- ⚠️ 按任务授权改动 `frontend/src`（新页面/路由/PageType/侧栏为本功能必需，另 `LearningResource.tsx` 追加 2 处 mindmap/code 埋点、`VideoLecture.tsx` 追加可选 prop）——均为 additive，未改 Zustand store 结构、未删除既有路由。
