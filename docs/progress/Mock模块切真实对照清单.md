# Mock 模块切真实对照清单

**项目：** 软件杯 · 领域知识个性化资源生成和多智能体系统
**整理日期：** 2026-06-15　|　**对照后端代码复核：** 2026-06-18
**依据：** 后端接口文档 + 后端执行方案 B0–B8 + 多模态方案设计；本次复核**逐接口核对了后端实际代码走的是 Mock 分支还是真实分支**。

> **前提说明**：前端各页面均已完成。底层数据 / 逻辑在 2026-06-15 时大多为 mock；**截至 2026-06-18，主链路与多数特色模块的真实管线已落地**（B5 讲义 / B7 工作流 / S9 学习路径 / 导学 / 视频分镜 / 图解 / 错题 / 学情概览均已切真实）。RAG 管道、认证、掌握度状态机、测验判分仍是真实实现，不在切换清单内。

## 复核要点（必读）

- **「真实管线」的判定口径**：服务层是否真正跑了 Agent / RAG / LangGraph 流程，而非返回写死的字典或 `setTimeout` 假阶段。**经 `LLMClient`（`app/core/llm.py`）的 mock provider 返回结构化假数据、但流程为真，仍记为「已切真实」**——这正是 CLAUDE.md「Mock-first、无 Key 也能跑通全链路」的设计。
- **provider 开关**：`settings.llm_provider`（`core/config.py:29`）默认 `mock`；当前 `backend/.env` 配置为 `deepseek` 且带真实 Key，**线上态即走真实 DeepSeek 推理**。绝大多数接口对 deepseek 失败有 try/except 回落 mock，保证不崩。
- 一句话结论：**原 P0 四项已全部切真实；P1/P2 中仅「外部资源聚合」「岗位市场」仍为静态 Mock；「讲解视频」「知识图谱」为半真实。**

**状态图例：** ✅ 已切真实（管线为真）　🟡 半真实（部分为真 / 仍有静态成分）　⛔ 仍 Mock（纯静态，无 Agent）

---

## 一、核心链路（P0 · 原"重灾区"，**现已全部切真实**）

| 模块 / 接口 | 状态 | 复核结论（file 证据） |
|---|:--:|---|
| 画像解析 `/profile/parse` | ✅ | 走 `LLMClient.extract_profile`（`services/profile.py:100`）；无材料标 `manual` 且**不调 LLM 防臆造**（profile.py:99）。mock/deepseek 双分支均真实。 |
| 画像叙述 `/profile/narrative` | ✅ | 走 `LLMClient.generate_narrative`（profile.py:126）；无材料返回 `None`（profile.py:121）；deepseek 分支对 sourceId 做白名单防引用不存在材料。 |
| **自适应讲义** `/resource/lecture` | ✅ | 真实路径走 `run_learning_workflow`（`services/resource.py:446`）：RAG 检索 → 生成 Agent → 审核 Agent；**sources 来自真实检索命中、幻觉率由 `sentence_grounding` 真算**（critic_agent.py:60）。mock 路径才用固定 3 源 + 0.021 兜底。 |
| **多智能体工作流** `/workflow` | ✅ | 真实 **LangGraph 五节点状态机**（diagnostic→retrieval→generation→validation→decision，`workflows/learning_workflow.py:308`），含 `score<0.8` 重试与降级；trace 经 **WS 增量帧实时推送**点亮大屏（`api/v1/workflow.py:97`、`services/workflow_runner.py`），非 setTimeout。 |

> 这组是"诊断 → 生成 → 审核"主链路，评委最爱追问的「Agent 真在协同吗、幻觉率怎么算」——现已可现场演示真实 LangGraph 执行与逐句 grounding。

---

## 二、特色与资源模块（P1）

| 模块 / 接口 | 状态 | 复核结论（file 证据） |
|---|:--:|---|
| 苏格拉底导学 `/resource/tutor/chat` | ✅ | 真实 Agent + **SSE 流式**（`services/tutor.py:76,96`→`LLMClient.tutor_chat[_stream]`），system prompt 强约束"只提问不给答案"；mock 为关键词分支 + 字符级流式兜底。 |
| 外部资源聚合 `/resource/external` | ⛔ | **仍静态**：读 `ExternalResource` 种子库（6 核心 KP × 3-4 条，`services/resource.py:74-107`），无聚合 Agent、无外部 API。生产路径（YouTube/B站/arXiv 检索 + critic 评分）仍待实现，**性价比最低、可留到最后**。 |
| 讲解视频 `/resource/video` | 🟡 | **分镜脚本已真实化**：`LLMClient.generate_video_script` 按知识点动态生成场景/旁白（resource.py:310）。但**视频仍前端 Remotion 渲染 + 浏览器 TTS 演示**，`videoUrl` 返回 null（resource.py:326）；服务端 TTS（edge-tts/Azure）+ `@remotion/renderer` 导出 mp4 仍未做。 |
| 知识图解（Mermaid）`/resource/diagram` | ✅ | `LLMClient.generate_diagram` 真实生成 Mermaid，失败回落模板（llm.py:1137）。 |
| 思维导图（Mindmap） | 🟡 | 后端 `_MINDMAPS` 仍为静态大纲；**但联调态前端由真实讲义 markdown 结构化**（`lectureOutline(activeLecture)`），内容随知识点变化。后端动态生成可选补。 |
| 错题强化 `/reinforce` | ✅ | `LLMClient.generate_reinforcement` 真实诊断薄弱点 + **内置 critic 审核重试**（quiz.py:131-135、llm.py:1235）；mock 为确定性变式。双模式同等校验。 |

> 新增已真实（原清单未单列，属 C2 学习流）：**康奈尔线索** `/learning/cornell-cues` ✅（llm.py:1363，失败回落模板）、**费曼评估** `/learning/feynman` ✅（llm.py:1500，SSE 流式 + 缺口诊断）。

---

## 三、数据与展示模块（P1 / P2）

| 模块 / 接口 | 状态 | 复核结论（file 证据） |
|---|:--:|---|
| 岗位市场 `/job-market` | ⛔ | **仍静态快照**：读 `JobSnapshot`（启动时由 `public/data/job-market/*.json` 种子载入），skills 频率 / radar 维度写死，无 LLM 抽取。已补「手动填写岗位」入口，但数据源未接离线采集管线。 |
| 知识图谱 `/knowledge-graph` | 🟡 | **半真实**：12 节点 / 14 边结构静态，但每个节点 **category/value 由真实掌握度实时派生**（`services/knowledge_graph.py:73-100`，passed→已掌握、seed<20 未started→盲区）。动态扩充节点 + 真实关系抽取仍未做（兼打 C 赛题时再上）。 |
| 学情概览 `/dashboard/overview` | ✅ | **已切真实**：radar / 优势 / 盲区 / 综合分 / 图谱覆盖率 **全部由真实 `StudentPortrait` + 掌握度聚合**（`services/dashboard.py:84-155`，注释明令"禁止臆造"，空画像返回 0 而非默认值）。 |
| 学习路径生成 `/learning-path/generate` | ✅ | **已切真实**：`planner_agent` 按真实画像 / 掌握度 / 岗位需求打分排序（planner_agent.py:174-216，稳定排序可复现），非 1.5s 假完成；理由文案 mock 走模板、deepseek 走 LLM。结果落 `Journey.path_plan`。 |
| 环境卡片（时钟 / 天气 / 贴士） | — | 前端本地生成，**无需切**（天气可选接第三方，不影响评审）。 |

---

## 四、已经是真实的（无需切换）

RAG 管道（chunker + embedding + Chroma + 混合检索 + rerank + 逐句 grounding）、JWT 认证、掌握度 / 旅程状态机、测验判分、难度自适应切换的前端逻辑、管理端（知识库管理 / Prompt 热更新 / 指标看板）——底层均真实，仅部分初始数据来自种子库。

**本次复核新确认为真实的**（2026-06-15 清单尚标 mock）：讲义、工作流、学习路径、苏格拉底导学、视频分镜、Mermaid 图解、错题强化、学情概览、康奈尔线索、费曼评估。

---

## 五、当前仍待切真实的清单（收敛后）

| 优先级 | 模块 | 仍缺什么 | 工作量 |
|:--:|---|---|:--:|
| 体验加分 | 思维导图后端动态生成 | 后端按 KP 出大纲（目前前端从讲义结构化已够用） | 小 |
| 体验加分 | 讲解视频服务端化 | 接 TTS 服务 + `@remotion/renderer` 导出 mp4（当前前端渲染 + 浏览器 TTS） | 中 |
| 揭榜挂帅(C) | 外部资源聚合 | 聚合 Agent 调外部 API + critic 评分写回（当前静态种子库） | 大 |
| 揭榜挂帅(C) | 岗位市场 + 动态知识图谱 | 离线采集管线 + LLM 抽取 / 动态节点与关系抽取 | 大 |

> 原"推荐切换顺序"中第 1（错题强化）、第 2（讲义 + 工作流）、第 3（导学）均已完成；剩余项均为体验加分或 C 赛题专属，**P0/P1 演示链路已无 mock 短板**。

---

## 六、重要提醒

- 上表状态以 **2026-06-18 后端实际代码**为准；判定口径见「复核要点」。若后续改动服务层分支，请同步本表。
- `backend/.env` 当前 `LLM_PROVIDER=deepseek` 并内含真实 API Key——演示前确认 Key 有效与额度；**离线 / 断网演示**时改回 `mock` 即可全链路跑通（默认值就是 mock）。
- 安全提醒：真实 Key 不应随源码外传，确认 `.env` 已在 `.gitignore` 内。

---

*本清单依据后端实际代码复核整理；具体实现以代码为最终依据。*
