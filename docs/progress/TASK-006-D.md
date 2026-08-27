# TASK-006-D 前端页面级懒加载与大包治理

## 完成状态

已完成。保持现有 `PageType`、状态路由、Zustand Store 和导航语义不变，将欢迎页、登录页、学习端页面、管理端页面及全局辅导层改为 `React.lazy` 页面级加载，并统一提供 `Suspense` 加载态。

本阶段仅完成 TASK-006-D，未进入 TASK-006-E。新增文件 2 个，符合每阶段新增文件不超过 8 个的约束。

## 治理结果

- 基线入口：`3,761.81 kB`，gzip `1,215.72 kB`。
- 最终入口：`319.03 kB`，gzip `105.65 kB`。
- 原始体积下降 `3,442.78 kB`，约 `91.5%`；gzip 下降 `1,110.07 kB`，约 `91.3%`。
- 欢迎页、登录页、Dashboard、LearningResource、DocumentLearning、KnowledgeGraph 与管理端均生成独立页面 chunk。
- ECharts 与 Remotion 形成独立按需 vendor chunk；Markmap、Markdown/KaTeX 和语法高亮随其页面/能力边界天然按需拆分，避免强制分组造成循环 chunk。
- `dist/index.html` 不包含上述重型 vendor 的 `modulepreload`，避免仅缩小入口文件但仍在首屏提前下载重包。
- Mermaid 保留其内置按图型动态拆分，未强行合并成单一超大包。
- 新增入口 `400 KiB` 和首屏重型 vendor preload 自动门禁。

构建仍提示若干按需 chunk 大于 500 kB，主要为 Mermaid 特定图型、语法高亮、登录页视觉依赖和 ECharts；这些产物不在首屏 HTML 静态预加载链中，后续若需继续拆能力边界应归入 TASK-006-E，不能在本阶段顺手重构页面业务。

## 文件清单

新增：

- `frontend/scripts/check-bundle-budget.mjs`
- `docs/progress/TASK-006-D.md`

修改：

- `frontend/src/App.tsx`
- `frontend/src/styles/App.css`
- `frontend/vite.config.ts`
- `frontend/package.json`
- `docs/维护/工作任务清单.md`
- `docs/维护/当前工程状态.md`

未修改现有 Zustand Store、路由结构、接口契约和前端数据获取层；工作区原有欢迎页、登录页、侧边栏、PPT、截图等未提交改动均予以保留且不纳入本阶段提交。

## 启动命令

```powershell
cd frontend
npm.cmd run dev
```

生产产物预览：

```powershell
cd frontend
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 4173
```

## 验证命令与实测结果

生产构建：

```powershell
cd frontend
npm.cmd run build
```

结果：退出码 0；TypeScript 0 error；Vite `4741 modules transformed`，最终构建成功。

包体门禁：

```powershell
cd frontend
npm.cmd run check:bundle
```

结果：退出码 0；`Bundle 预算检查通过：入口 317.23 KiB；首屏重型 vendor preload 0 个`。

生产预览 HTTP 回归：

```text
GET http://127.0.0.1:4173/                         -> 200
GET http://127.0.0.1:4173/assets/index-DWAPb1Bt.js -> 200
首屏重型 vendor modulepreload                     -> 0
关键页面 chunk（欢迎、登录、Dashboard、学习资源、文档学习、知识图谱、管理端）均存在
```

当前执行环境未提供可控浏览器实例，无法完成自动视觉点击回归，因此不将视觉回归虚报为已执行；生产构建、入口依赖链、HTTP 可访问性和关键页面产物检查均已通过。涉及页面业务与 Store/路由的代码未改动，回归风险限定在异步加载边界。

## 验收结论

- 未改变 Store 或路由结构。
- 生产构建 0 error。
- 首屏入口体积显著下降，且重包不再由入口 HTML 提前 preload。
- 页面代码均可生成独立生产产物，预览入口与入口脚本 HTTP 200。
- 自动视觉点击回归受当前浏览器环境限制，已明确记录；其余可执行验收项全部通过。
