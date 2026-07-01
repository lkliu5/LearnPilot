# 文档学习前端页面 · 完成总结

对接「会话一」后端的平行独立链路（接口文档第 20 章 + 19.1 增补：上传文档 → 独立向量集合 →
基于文档生成）。参考 NotebookLM 的「来源 / 生成 / 产出」信息架构，但完全套用项目现有设计令牌与风格。

## 一、文件清单

### 新增（5）
| 文件 | 说明 |
| --- | --- |
| `frontend/src/services/documentLearning.ts` | 数据获取层：上传/列表/详情/删除 + 六类生成（讲义/视频/图解/思维导图/练习题/闪卡）。联调走后端 `/document/*`，mock 全程本地合成（读文件正文 → 派生溯源可见的假产物），无后端/Key 可跑通全链路。 |
| `frontend/src/components/FlashcardDeck.tsx` | 新做闪卡组件：正/背面 3D 翻转卡片 + 整套翻页浏览（点击/空格/回车翻面，← → 翻页，圆点跳转），复用 `exportLectureMarkdown` 导出整套闪卡。 |
| `frontend/src/components/FlashcardDeck.css` | 闪卡样式（纯设计令牌 · 深浅主题自适应 · 移动端适配）。 |
| `frontend/src/pages/DocumentLearning.tsx` | 页面：左「来源区」（拖放/点击上传 + 文档列表 + 状态/删除），右「生成 + 产出区」（六类操作卡 + 复用渲染组件的产出视图）。 |
| `frontend/src/pages/DocumentLearning.css` | 页面样式（仅 `doclearn-*` 新类；空状态、拖放区、操作卡、产出区、响应式）。 |

### 修改（2）
| 文件 | 改动 |
| --- | --- |
| `frontend/src/App.tsx` | `PageType` 增 `'document-learning'`；导入 `DocumentLearning`；`renderPage` 增 case。 |
| `frontend/src/components/Sidebar.tsx` | 「总览与工具」组新增「文档学习」入口 + 配套渐变图标 `icons.docLearn`。 |

> 复用（未改动）：`MarkdownRenderer`、`VideoLecture`（受控模式传 scenes）、`MermaidDiagram`、`MindMap`、
> `QuizRenderer`、`SourceTrace`、`PageHeader`、`exportLectureMarkdown/exportLectureToPdf`、
> `downloadSvg(AsPng)`（图解/导图内置导出）。`DocumentLearning.tsx` 复用 `pages/LearningResource.css`
> 中的共享样式类（`.lecture-export`/`.level-switch`/`.resource-loading` 等，均为 class 前缀、无全局副作用）。

## 二、接口文档增量

**无。** 完全消费接口文档已定义的第 20 章（20.1–20.7）与 19.1 增补（`source=document` / `kind=quiz|flashcard`），
字段名严格对齐，未新增或改动任何契约。

## 三、启动与验证命令

```bash
# 后端（会话一，需重启以加载 /document/* 路由）
cd backend && uvicorn app.main:app --port 8000
# 前端（联调开关 VITE_USE_REAL_API=true）
cd frontend && npm run dev          # 本次实测端口 3002（3000/3001 被占用自动顺延）
```

## 四、验证结果（联调真实后端，learner_001）

- **tsc**：`npx tsc --noEmit` → **EXIT=0**（0 报错）。
- **上传 → 选中 → 生成**：上传 `泽塔向量收敛定理.md` → 后端解析入库置「就绪」→ 自动选中 →
  逐一生成 **讲义 / 图解 / 练习题 / 闪卡**，内容确为该文档所出（如练习题「泽塔权重 w_n 必须满足什么条件才能保证能量有界？」、
  闪卡背面「当泽塔权重满足单调递减且平方可和时…收敛到唯一极限点」= 文档原句）。
- **闪卡**：正/背面翻转正常（「问」→「答」）、← → 翻页、圆点跳转均可用。
- **下载**：闪卡「下载闪卡」→ `闪卡-泽塔向量收敛定理.md`（整套 7 张 Q/A）成功导出；讲义导出条（Markdown/PDF）、
  图解/导图内置 SVG·PNG 导出复用既有能力。
- **进资源库**：生成后「我的资源库」出现对应「泽塔向量收敛定理 · 定制讲义/知识图解」等记录（后端 `source=document` 自动埋点），可查看/下载。
- **主题**：鼠尾草 / 墨纸 两套主题切换后本页与组件均正常（全程用设计令牌）。
- **console**：文档学习页、内置学习资源页、资源库页均 **0 error**。
- **无回归**：内置「学习资源」页照常渲染（讲义/导出/标签/即时辅导等无异常）。

> 说明：讲义内嵌 Mermaid 与「知识图解」在本演示文档（含 `<∞`、`^`、`[]` 等数学符号）下由后端 mock 生成的
> Mermaid 语法非法，触发 `MarkdownRenderer` / `MermaidDiagram` **既有的错误兜底 UI**（非本页缺陷，非 console error，
> 与内置课程页同组件同行为）。属后端生成内容质量项，前端已优雅兜底。

## 五、红线自检

- ✅ 未改 `frontend/src` 业务逻辑 / Zustand store 结构 / 路由机制（仅在既定扩展点新增页面与入口）。
- ✅ 未改任何接口路径/字段/枚举；仅消费第 20 章既有契约。
- ✅ mock-first：`VITE_USE_REAL_API=false` 时全链路本地兜底可跑（读文件正文派生溯源可见产物）。
- ✅ 复用现有渲染与下载组件、设计令牌；未重构已验收阶段代码。
- ✅ 未新增重型依赖；闪卡为纯 CSS 3D + framer-motion。
- ⚠️ 运维旁注：`:8000` 上原有后端进程为「会话一提交前」的旧实例（`/document/*` 返回 404），已重启加载新路由以完成联调；此为部署侧事项，非代码改动。
