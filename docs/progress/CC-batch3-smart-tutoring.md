# CC 批3-B — 智能辅导·按需资源生成（需求 1 · 赛题功能 4）

> 学生卡住 → 识别问题点 → 针对性资源生成清单 → 勾选 → 按需生成对应资源并查看。
> 复用现有苏格拉底/导学对话 + 讲义/图解/视频/例题生成能力；新增清单接口套信封；mock 兜底。

═══════════════════════════════════════════════════════════════

## 文件清单
**新增（5）**
- `backend/app/services/tutor_resource.py`：辅导资源编排——`suggest`（识别问题点 + 清单）、
  `generate`（勾选类型 → 复用 diagram/video/lecture/example 逐项生成）。
- `backend/tests/test_tutor_resource.py`：suggest/generate 契约 + 过滤去重 + 1004 共 6 用例。
- `frontend/src/services/tutorResource.ts`：`suggestResources` / `generateResources`（联调 + mock 兜底）。
- `frontend/src/components/TutorResourcePanel.tsx`（+ `.css`）：清单勾选 + 生成 + 内联查看
  （复用 `MermaidDiagram` / `MarkdownRenderer`）。

**修改**
- `backend/app/core/llm.py`：新增 `LLMClient.suggest_remedial_resources`（识别问题点 + 清单，
  mock 关键词 / deepseek 真实）、`generate_remedial_content`（例题 / 讲义片段，mock/deepseek）。
- `backend/app/schemas/resource.py`：新增 `TutorSuggestRequest` / `TutorGenerateRequest`。
- `backend/app/api/v1/resource.py`：新增 `POST /resource/tutor/suggest` + `/generate`（套信封）。
- `frontend/src/components/SocraticTutor.tsx`：加「🆘 我没懂」触发 + 渲染资源面板（记录上一问）。

## 接口文档增量（`docs/后端接口文档.md`，追加不重排）
- 8.8（新增）`POST /resource/tutor/suggest`（问题点 + 资源清单）+ `POST /resource/tutor/generate`
  （按需生成，results 复用 8.5/8.3/8.2/例题）。
- 13 接口总览表：新增第 22b / 22c 行。

## 验证结果（live 实测 + 测试 + UI 走查）
1. **抛问题 → 资源清单**：`POST /resource/tutor/suggest {kpId:nn, question:"激活函数到底有什么用，我没懂"}`
   → deepseek 识别问题点 + 4 项清单（图解/例题/短视频/补充讲义片段），每项标注类型 + 预计内容。
   mock：关键词识别「激活函数与非线性」+ 模板清单。
2. **勾选 → 按需生成并查看**：`POST /resource/tutor/generate {types:[diagram,example,lecture]}`
   → diagram 复用 8.5（mermaid flowchart）、example（题干 + 分步解析）、lecture（markdown 片段）；
   未知 type 剔除 + 按类型去重；空选 → results 空。
3. **UI 走查（联调 deepseek）**：导学对话 →「🆘 我没懂」→ 面板显示识别问题点 + 4 项勾选清单 →
   「生成所选(4)」→ 内联渲染 知识图解(Mermaid SVG) + 例题(含「查看解析」) + 短视频(5 分镜) +
   补充讲义片段(Markdown)。**浏览器 0 console error**。
4. **回归 + 类型**：`pytest` **191 passed, 1 skipped, 0 失败**；`tsc --noEmit` **0 报错**；mock 可跑。

## 红线自检
- 既有接口签名未改：仅**新增** `/resource/tutor/suggest` + `/generate`；既有 `/resource/tutor/chat`
  及讲义/图解/视频接口逐字不变。
- 统一信封：新增接口套 `{code,message,data,traceId}`。
- 复用优先：按需生成全部复用既有 `resource.diagram/generate_video` + `LLMClient`，未重建生成链路。
- Mock/真实双模式：问题点识别、清单、例题/讲义片段均双模式；无 Key 不崩（mock 兜底）。
