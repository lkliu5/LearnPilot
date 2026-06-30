# 讲义功能：表格渲染修复 + 讲义导出（.md / .pdf）

> 纯前端增量 + 一处后端生成 prompt 增强；**不改任何已定义接口签名**（新增能力均为前端本地能力）。

## 一、现状说明（问题定位）

1. **表格渲染错乱**：前端 Markdown 渲染管线（`MarkdownRenderer.tsx`）只挂了 `remark-math` + `rehype-katex`，
   **缺少 `remark-gfm`** → GFM 表格 `| --- |`、删除线、任务列表语法不被解析，表格被当普通文本，显示错乱。
   且 `.markdown-body` 无表格 CSS。
2. **无讲义导出入口**：讲义详情没有导出 .md / .pdf 的能力。
3. **PDF 方案选型约束**：本项目主题大量使用 CSS `color-mix()`（globals.css 约 20 处），而
   `html2canvas / jsPDF+html2canvas / html2pdf.js` **无法解析 `color-mix()/oklch()`**（会抛
   "unsupported color function" 直接失败）。故 PDF 采用**自包含打印窗口**方案：克隆"已渲染"的讲义 DOM
   到一个注入了干净打印样式 + 页面内 KaTeX 样式的新窗口，调浏览器原生打印 → 另存为 PDF。
   对公式(KaTeX HTML)、图解(mermaid SVG)、图片、表格保真最好，文字可选中、原生分页、无跨域污染。

## 二、改动文件清单

### 前端（frontend/）
- `package.json` / `package-lock.json`：新增依赖 `remark-gfm@^4`。
- `src/components/MarkdownRenderer.tsx`：
  - `remarkPlugins` 加入 `remarkGfm`（顺序 `[remarkGfm, remarkMath]`，不影响公式解析）；
  - 新增 `table` 组件渲染：包一层 `.md-table-wrap` 横向滚动容器，宽表不撑破布局。
- `src/pages/LearningResource.css`：新增 `.markdown-body .md-table*` 表格排版（表头底色、描边、斑马纹、
  宽表横向滚动）、删除线、任务列表复选框样式；新增 `.lecture-export*` 导出工具条样式。
- `src/utils/lectureExport.ts`（**新增**）：
  - `exportLectureMarkdown(content, baseName)`：blob 下载 .md 原文；
  - `exportLectureToPdf(sourceEl, title, meta)`：自包含打印窗口导出 PDF（复用已渲染 DOM，注入打印样式 +
    KaTeX 样式，`<title>` = 建议文件名，原生 `print()`）；
  - `sanitizeFilename`：文件名清洗。
- `src/pages/LearningResource.tsx`：讲义详情（资源中枢·定制讲义 Tab）加导出工具条（Markdown / PDF 按钮）+ 处理函数；
  文件名 `讲义-{知识点}-{难度}`。
- `src/components/LearningFlow.tsx`：有序学习·定制讲义视图同样加导出工具条（复用同一导出工具），
  保证两种浏览模式下"讲义详情"都有导出入口。
- `src/pages/LearningResource.tsx`（mock 演示内容）：将"常见激活函数"无序列表改写为 GFM 对比表格，
  作为 mock 兜底下的表格渲染演示（仅演示数据，不涉业务逻辑）。

### 后端（backend/）
- `app/services/prompts.py`：`generation` 默认模板新增「表格格式」铁律（对比/多维信息一律用标准 GFM 表格，
  `| --- |` 分隔、单元格数对齐、不在格内换行）；并把改动前的模板登记为历史默认 `_GENERATION_V2`，
  纳入 `_PRIOR_DEFAULTS` 自动升级集合（已落库的旧默认平滑升级，管理员自定义模板不被覆盖）。

## 三、接口文档增量

**无。** 导出为纯前端本地能力，不新增/不修改任何后端接口；后端仅调整了 `generation` Agent 的
**默认 prompt 模板内容**（经既有 14.5 GET/PUT 接口管理，接口签名/字段/枚举均未变）。

## 四、验证结果

构建与类型：
- `npx tsc --noEmit` → **exit 0**（干净）。
- `npm run build` → **exit 0**（仅既有 chunk 体积告警，与本次无关）。
- 后端 `pytest tests/test_admin_prompts_metrics.py tests/test_workflow_b5a.py tests/test_contract_snapshot.py -q`
  → **57 passed**。

三项截图验证（Playwright，端口 3001）：
1. **表格渲染**（mock 模式，初级讲义）：「常见激活函数」对比表正确渲染为表格——表头
   `激活函数/公式/输出范围/适用场景`，描边 + 斑马纹 + 格内行内代码；DOM 校验 4 行 4 列。✓
2. **导出 .md**：点击 Markdown → 下载 `讲义-神经网络基础-初级.md`，内容以 `# 神经网络基础` 开头、
   含 GFM 表格 `| 激活函数 |`、结尾完整（1041 字符全量原文）。✓
3. **导出 .pdf**：点击 PDF → 生成自包含打印文档：`<title>讲义-神经网络基础-初级`、含打印样式 + KaTeX 样式 +
   表格 + 代码块 + 顶部 meta（知识点·难度·导出时间）+ `window.print()`；预览渲染为白底深字、标题/列表/
   引用/代码块/表格结构完整、公式可读。✓
4. **不受影响 / 无回归**（real-API 模式真实讲义）：同一讲义渲染 **50 处 KaTeX 公式 + 1 个 mermaid 流程图 +
   1 张配图** 全部正常，导出入口正常；**当前页 0 console error / 0 warning**。✓

## 五、红线自检

- ✅ 未改任何已定义接口的路径/字段/枚举；导出为纯前端，无新增后端接口。
- ✅ 未改前端业务逻辑 / Zustand store / 路由；仅在讲义渲染与详情视图追加渲染与导出能力。
- ✅ Mock-first 保持：mock 模式下表格 + 两种导出全部可跑通（无需任何 Key）。
- ✅ 复用现有讲义渲染（`MarkdownRenderer`）；PDF 导出"当前已渲染内容"，不重新请求生成。
- ⚠️ 已知（非本次引入、超出范围）：mock 内容个别 `**…（全角括号）**` 因 CommonMark CJK 强调与全角标点相邻的
  既有规则不解析为加粗（与是否加 remark-gfm 无关，real 模式真实讲义不受影响）；未在本次扩大范围去改。
