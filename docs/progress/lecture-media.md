# 讲义图文并茂（图解优先 + 真实图片补充 + 防幻觉/兜底）

## 目标

给讲义插入图片，使内容图文并茂；不改后端接口签名（新增仅追加并同步文档）；
禁止 AI 生成图片；mock 模式用确定性占位、不发真实搜索；内容安全/防幻觉不绕过。

## 图源策略（双来源 + 兜底）

1. **图解优先（最稳、无版权、必贴题）**：结构/流程类小节复用既有 Mermaid 图解能力
   （`LLMClient.generate_diagram`，mock 确定性、离线可渲染），以 ```mermaid 围栏内嵌「核心原理」小节末尾。
2. **真实图片补充**：适合配真实图处用已接入的 **Tavily 图片搜索**（`web_search.search_images`，
   `include_images`）。**图片 URL 只取自搜索结果**（沿用「URL 只取真实候选、防幻觉」原则，绝不让
   LLM 编造链接），并标注来源域名（出处链接）。无合适图 → 不插（宁缺毋滥）。
3. **禁止 AI 生成图片**（教育内容画错风险高）。
4. **mock 模式不发真实搜索**：用确定性 base64 内联 SVG 占位图（自包含、永不 404、无网络）。

## 改动文件清单

### 后端（新增 1 个文件 + 3 处追加，接口签名不变）
- `backend/app/core/lecture_media.py`（**新增**）：`enrich_lecture()` 注入图解 + 配图；
  幂等（末尾 `<!-- media:enriched -->` 标记，不破坏正文以 `# ` 开头的契约）；图解失败/无图均不致命。
- `backend/app/services/web_search.py`（**追加** `search_images()`：Protocol + Offline + Tavily 三处，
  `search()` 原签名不变）。
- `backend/app/services/resource.py`（在 `generate_lecture` 与 `cache_lecture_from_workflow`
  两条讲义出口各调用一次 `enrich_lecture`；新增 `from app.core import lecture_media`）。

### 前端（讲义渲染层，业务逻辑/store/路由未改）
- `frontend/src/components/MarkdownRenderer.tsx`：① ```mermaid 围栏走懒加载 `MermaidDiagram`；
  ② 新增 `img` 处理器 `MarkdownImage`（懒加载失败 `onError` → 优雅占位「🖼️ 图片暂不可用」，不显破图）；
  ③ `urlTransform` 放行自包含 `data:image/` 占位图；④ `pre` 包裹为 `div.md-codeblock` 避免无效嵌套。
- `frontend/src/pages/LearningResource.css`：内嵌图解/配图/裂图占位样式（`.md-image` / `.md-image-fallback`
  / `.markdown-body .mermaid-diagram` / `.md-codeblock` / `.mermaid-loading`）。

### 文档
- `docs/后端接口文档.md` 8.2：增量说明（字段/路径不变，markdown 现内嵌 mermaid+配图+来源标注）。

### 测试（随契约更新，非回归）
- `backend/tests/test_b5b.py`：两处讲义 markdown 断言由「逐字等价」改为「核心内容 + 确定性图文增强」
  （mock：`== enrich_lecture(core,...)` 且含 ```mermaid 与 data:image；真实：`startswith(grounded_md)` 且含 ```mermaid）。

## 启动命令

```bash
# 后端（mock 全链路，无需任何 Key）
cd backend && set LLM_PROVIDER=mock&& set SEARCH_PROVIDER=none&& uvicorn app.main:app --port 8000
# 前端（联调真实后端：VITE_USE_REAL_API=true）
cd frontend && set VITE_USE_REAL_API=true&& npm run dev   # http://localhost:3001
```

## 验证结果（实测）

### 单测/类型
- `cd backend && pytest -q` → **208 passed, 1 skipped**（0 报错）。
- `cd frontend && npx tsc --noEmit` → **exit 0**（tsc 干净）。

### 端到端（mock 模式，Playwright 实测，0 console error）
- 讲义「神经网络基础」渲染（DOM 实测）：
  - **mermaidCount=1，已渲染 SVG**（位于「核心原理」小节，caption「核心结构/流程示意（系统生成图解）」）；
  - **imgCount=1**，`data:image/svg+xml;base64`，naturalWidth=720/Height=360，`complete=true`（位于「概念引入」，
    caption「示意图（mock 占位，未发起真实搜索）」）；
  - 末尾含 `<!-- media:enriched -->` 标记。
- **裂图兜底**：将图片 src 改为无效 URL → 破图 `<img>` 从 DOM 移除，替换为占位「🖼️ 图片暂不可用」，
  **不显示浏览器破图**（唯一 console error 为故意置坏 URL 触发的网络请求日志，正是 `onError` 的触发源）。
- **不强插**：配图只放「概念引入」，其余小节不塞图；mock 占位为确定性 SVG，未发任何真实搜索请求
  （`SEARCH_PROVIDER=none`）。

### 截图（项目根目录）
- `lecture-mermaid-diagram.png`：核心原理小节内嵌 mermaid 图解（KaTeX 公式下方）。
- `lecture-placeholder-image.png`：概念引入小节配图（mock 占位卡片 + 来源/说明 caption）。
- `lecture-broken-image-fallback.png`：裂图优雅占位（无破图）。

## 红线自检
- ✅ 不改后端接口签名/路径/字段/枚举（8.2 仅追加增量说明；`search_images` 为内部追加方法）。
- ✅ 禁止 AI 生成图片：图解=Mermaid 复用，真实图=Tavily 搜索，占位=确定性 SVG，**无任何生成式画图**。
- ✅ 防幻觉：真实图片 URL 只取自搜索结果并二次校验 http(s)，绝不由 LLM 产出链接；真实图标注来源。
- ✅ 内容安全不绕过：核心讲义/图解经 `LLMClient` guard，外部图片描述另过 `content_safety.guard`。
- ✅ Mock-first：无任何 API Key 跑通全链路（图解离线、占位内联、不发真实请求）。
- ✅ 未改 `frontend/src` 业务逻辑/store/路由；仅改讲义渲染组件与样式（任务明确要求前端支持图片展示）。
- ✅ 0 报错：208 passed / tsc 0 / 0 真实 console error。
