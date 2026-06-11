# B4-b — Prompt 管理 + 指标看板 · 完成总结

> 阶段：B4 后半（B4-b）｜状态：✅ 完成（0 报错）｜日期：2026-06-11
> 范围：后端 14.5 GET/PUT `/admin/prompts/{agentId}` + 14.6 GET `/admin/metrics`
> + Prompt 管理页（三 Agent 模板编辑、保存即热更新）+ 指标看板页（三 gauge × CountUp）。

## 1. 交付内容

### 后端 · 14.5 Prompt 模板热更新（`services/prompts.py` + `api/v1/admin_prompts.py`）

- **GET** `/api/v1/admin/prompts/{agentId}`：返回 PromptTemplate 全量
  `{agentId, name, template, variables, version, updatedAt}`；首次访问对
  `diagnosis / generation / critic` 三 Agent 懒种子默认模板（幂等，version=1），
  name 与接口文档 11.2 `agents[].name` 逐字一致，generation 模板与 14.5 示例同构。
- **PUT** `/api/v1/admin/prompts/{agentId}`：占位符校验（`{var}` 形式，必须保留
  `variables` 全部项）→ version 自增 → `updatedAt` 刷新，返回
  `{agentId, version, updatedAt, hotReloaded: true}`。
- **热更新供 B5 消费**：模板存 SQLite（PromptTemplate 表，B1 已建），
  `services.prompts.get_template(db, agent_id)` 每次现读 DB、无进程内缓存——
  PUT 后下一次生成调用立即生效，无需重启。
- 错误口径：缺失占位符 → `1001/400`（message 列出缺失项）；未知 agentId →
  `1004/404`；非管理员 → `1003/403`（复用 `require_admin`）。

### 后端 · 14.6 系统指标看板（`api/v1/admin_metrics.py`）

- **GET** `/api/v1/admin/metrics`：结构按契约定死
  `{hallucinationRate, adaptationRate, coverageRate, kbDocuments, kbChunks, generatedResources, updatedAt}`。
- 三比率为 **B8 前占位常量**（取接口文档 14.6 示例值 0.021 / 0.87 / 0.92），
  B8 接入 15.3 逐句接地口径与统计脚本时仅替换取值逻辑、结构不变；
  三计数为 DB 实时统计（KnowledgeDocument 行数 / chunks 求和 / ResourceCache 行数）。

### 前端 · Prompt 管理页（`pages/admin/AdminPrompts.tsx`）

| 功能 | 实现 |
|---|---|
| 三 Agent 页签 | diagnosis / generation / critic 卡片页签（agentId mono 徽章 + 中文名 + 职责说明），切页签不丢未保存编辑 |
| 模板查看 | 名称 + `v{version}` mono 版本徽章 + 更新时间 + 必需占位符 chips |
| 编辑 | mono 等宽 textarea；编辑中显示「未保存」徽章；缺失必需占位符时对应 chip 变红、保存按钮禁用并提示（与后端 1001 校验同口径前置拦截）；「还原」回滚到已保存版本 |
| 保存 | PUT 成功后**就地刷新新版本号与更新时间**，toast「已保存并热更新 · 版本 v{n}」 |

### 前端 · 指标看板页（`pages/admin/AdminMetrics.tsx`）

- 三 gauge 半环仪表（SVG 弧 + Framer Motion 弧长入场）：幻觉率（目标 <5%）/
  适配率（≥85%）/ 覆盖率（≥90%），中心数字**复用 `CountUp` 组件 + mono 字体**，
  按达标口径显示「达标/未达标」徽章（复用全局 agent-status 视觉）、未达标弧变琥珀色。
- 计数统计行：知识库文档 / 向量切片 / 已生成资源三计数（同样 CountUp + mono）+ 统计时间。
- 两页均沿用 B4-a 约定：mock 模式（未设 `VITE_USE_REAL_API=true`）显示联调提示条、
  不发请求、无控制台报错；样式续用 `admin.css`（新增 `apr__` / `amx__` 前缀，全部引用既有设计令牌）。

## 2. 文件清单

新增 6 个（≤8 上限）：

| 文件 | 说明 |
|---|---|
| `backend/app/services/prompts.py` | 模板默认种子（懒、幂等）+ 读写 + 占位符校验 + B5 消费入口 `get_template` |
| `backend/app/api/v1/admin_prompts.py` | 14.5 GET/PUT 路由（require_admin / 1001 / 1004） |
| `backend/app/api/v1/admin_metrics.py` | 14.6 指标路由（占位比率 + DB 实时计数） |
| `backend/tests/test_admin_prompts_metrics.py` | 11 条契约测试（TDD：先写并实测 RED，9 failed→实现→全绿） |
| `frontend/src/pages/admin/AdminPrompts.tsx` | Prompt 管理页 |
| `frontend/src/pages/admin/AdminMetrics.tsx` | 指标看板页 |

删除 1 个：`frontend/src/pages/admin/AdminPlaceholder.tsx`（B4-a 占位页，本阶段被实装页替换，无引用残留）。

**既有文件改动（单独列出，按 CLAUDE.md 要求）**：

| 文件 | 改动 | learner 侧影响 |
|---|---|---|
| `backend/app/main.py` | 挂载 admin_prompts / admin_metrics 两路由 | 无 |
| `frontend/src/services/admin.ts` | 数据获取层追加 14.5/14.6 类型与函数（仅 services 层，允许范围） | 无 |
| `frontend/src/App.tsx` | `admin-prompts` / `admin-metrics` 两 case 由占位页换成实装页（仅渲染分支，路由/守卫/PageType 均未动） | 无：learner 双保险拦截逻辑不变 |
| `frontend/src/pages/admin/admin.css` | 追加 `apr__` / `amx__` 样式块与响应式断点 | 无 |

## 3. 启动 / 验证命令

```bash
# 后端
cd backend && uvicorn app.main:app --port 8000
cd backend && pytest -q

# 前端（联调模式）
cd frontend && VITE_USE_REAL_API=true npm run dev    # Windows: $env:VITE_USE_REAL_API='true'; npm run dev

# 类型检查 / 构建
cd frontend && npx tsc --noEmit && npm run build
```

种子账号：`admin / admin123`、`learner_001 / 123456`。

## 4. 验证实测（0 报错）

### ① pytest（TDD：测试先行，先实测 9 failed RED，再实现转绿）

```
$ python -m pytest tests/ -q
19 passed in 1.98s        （11 条 B4-b 新增 + 8 条既有 chunker 测试，全绿）
```

### ② curl 实测（核心验收链路）

```
[admin GET /admin/prompts/generation]
  → code=0 agentId=generation version=2 vars=kpName,difficulty,ragContext

[admin PUT 改写 generation 模板]
  → {"code":0,"data":{"agentId":"generation","version":4,
     "updatedAt":"2026-06-11T03:56:52.339154","hotReloaded":true}}   ✅ 版本自增

[重新 GET]
  → version=4，template 与提交内容逐字一致（contentMatches=True）   ✅ 内容生效
    （services.prompts.get_template 与 GET 同一读取路径 → B5 生成链路同步拿到新模板）

[PUT 缺占位符模板]
  → {"code":1001,"message":"模板缺失必需占位符：difficulty, ragContext"} <HTTP 400> ✅
    （版本与内容不变，pytest 同口径断言）

[GET /admin/prompts/nope]
  → {"code":1004,"message":"Agent 不存在"} <HTTP 404> ✅

[GET diagnosis / critic]
  → version=1，vars=profileSummary,masteryStatus,targetJob / draftContent,ragContext ✅ 懒种子就绪

[admin GET /admin/metrics]
  → code=0 hallucination=0.021 adaptation=0.87 coverage=0.92
    kbDocs=5 kbChunks=43 genRes=3 updatedAt=2026-06-11T03:56:15+00:00 ✅ 计数为 DB 实时值

[learner 访问三接口（GET prompts / PUT prompts / GET metrics）]
  → 三次均 {"code":1003,"message":"无权限：需要管理员角色"} <HTTP 403> ✅
```

### ③ tsc / 构建

```
$ npx tsc --noEmit        → 无输出（0 错误）
$ npm run build           → ✓ built in 34.24s（chunk>500kB 提示为既有现象，非本阶段引入）
```

- 指标看板三 gauge / Prompt 编辑器渲染逻辑均由上述接口实测数据驱动，
  mock 模式打开两页不发请求、无控制台报错（与 B4-a 占位页同口径）；
  浏览器动效走查依赖人工，本机无浏览器自动化工具，以 tsc/build 0 报错 + curl 同口径数据背书。

## 5. 边界确认 / 给 B5 的约定

- **B5 消费入口**：生成链路取模板一律走 `app.services.prompts.get_template(db, agent_id)`
  （或 `get_prompt` 取全量），每次现读 DB，管理端 PUT 后即时生效，请勿在 B5 加进程内模板缓存。
- `variables` 为各 Agent 必需占位符的契约清单（存表、PUT 校验、前端 chips 三处同源），
  B5 渲染模板时按 `{var}` 直替即可。
- 指标三比率为占位常量已在 `admin_metrics.py` 顶部注释标注；B8 接真实计算时
  仅替换 `_PLACEHOLDER_RATES` 取值来源，响应结构与字段名不得变。
- 早期用 PowerShell 5.1 Invoke-RestMethod 直发中文 JSON 会因默认编码产生乱码模板
  （已被后续正确 PUT 覆盖）；联调请用前端页面或 `curl --data-binary @utf8文件`。
