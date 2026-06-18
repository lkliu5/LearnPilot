# C1 第一步 · 契约会话 — Claude Code 指令

> 用法：把下面「═══」之间的全部内容复制，发给 Claude Code。本会话**只改接口文档、不写实现代码**。

═══════════════════════════════════════════════════════════════

# 角色
你是资深后端架构师，正在为「软件杯·领域知识个性化资源生成与多智能体系统」补充接口契约。
项目已联调一轮，《后端接口文档.md》中现有 30 个接口已稳定、前端已切真实 HTTP。

# 本次任务范围（严格遵守）
- **只做一件事**：在《后端接口文档.md》中新增「对话式学习画像诊断」的接口契约章节。
- **禁止编写任何实现代码**（不动 backend/app、不动 frontend/src），本会话只产出接口文档的增量。
- **禁止修改任何已有的 30 个接口签名**，尤其是既有的知识能力雷达 `GET /profile/ability-portrait`——它供 Dashboard 使用，保持原样。本次新增的是「异质学生画像」，与它并存、不替换。

# 背景（为什么做这个）
赛题功能 1 原文要求：「摒弃传统繁琐表单，通过自然语言对话自动抽取特征，构建不少于 6 个维度（如知识基础、认知风格、易错点偏好等）的动态学生画像，并支持随学随新。」
当前画像模块是表单 + 滑块自评，需新增「对话式诊断」能力，故先定契约。

# 要新增的契约内容（请按文档现有风格、编号、信封规范整合进文档；字段可在保持语义下微调以对齐文档惯例）

## 1) 新接口：对话式诊断  `POST /api/v1/profile/dialogue`
- 与 8.7 苏格拉底辅导一致：请求头带 `Accept: text/event-stream` 时走 SSE 流式；否则返回整体 JSON（向后兼容）。
- 请求体：
```jsonc
{
  "sessionId": "d_123",          // 多轮上下文 id，首轮可空，由后端生成
  "message": "我是计算机本科，做过Python爬虫，想转大模型应用",  // 学生自然语言输入
  "context": { "major": "计算机科学", "goal": "职业培训" }      // 可选，首轮可带已知信息
}
```
- SSE 流式响应（Content-Type: text/event-stream）：
```
data: {"delta":"了解了。"}

data: {"delta":"你提到做过爬虫——那对 HTTP 和数据解析熟到什么程度？"}

event: portrait
data: {"updates":[{"key":"prior_experience","label":"先验经验","value":"有Python工程实践(爬虫)","confidence":0.8,"source":"dialogue"}]}

event: done
data: {"sessionId":"d_123","suggestions":["很熟能独立写","会用但常查文档","基本没接触"],"diagnosisComplete":false}
```
- 非流式响应 `data`：
```jsonc
{
  "sessionId": "d_123",
  "reply": "了解了。你提到做过爬虫——那对 HTTP 和数据解析熟到什么程度？",
  "portraitUpdates": [
    { "key": "prior_experience", "label": "先验经验", "value": "有Python工程实践(爬虫)", "confidence": 0.8, "source": "dialogue" }
  ],
  "suggestions": ["很熟能独立写","会用但常查文档","基本没接触"],
  "diagnosisComplete": false
}
```
- 约定（请写入文档）：
  - `delta` 逐条下发追问语；`event: portrait` 携带本轮抽取的画像维度增量（一次对话可多次）；`event: done` 结束，携带 `sessionId` + `suggestions` + `diagnosisComplete`。
  - 出错发 `event: error`，`data:{code,message}`，前端保留已渲染片段。
  - `sessionId` 会话上下文后端内存按 TTL 维持。
  - **防幻觉约束**：无法从对话判断的维度不得编造，`source` 取值 `dialogue | manual | inferred`，`inferred`（推断）须给较低 confidence。

## 2) 新数据结构：异质学生动态画像 StudentPortrait（≥6 维）
```jsonc
{
  "dimensions": [
    { "key": "knowledge_base",   "label": "知识基础",  "value": "一般", "score": 65, "confidence": 0.7, "source": "dialogue", "updatedAt": "..." },
    { "key": "cognitive_style",  "label": "认知风格",  "value": "偏实践/动手型",   "confidence": 0.6, "source": "dialogue" },
    { "key": "error_preference", "label": "易错点偏好","value": "概念易混淆",      "confidence": 0.5, "source": "inferred" },
    { "key": "learning_goal",    "label": "学习目标",  "value": "转大模型应用工程师","confidence": 0.9, "source": "dialogue" },
    { "key": "prior_experience", "label": "先验经验",  "value": "Python爬虫工程经验","confidence": 0.8, "source": "dialogue" },
    { "key": "learning_pace",    "label": "学习节奏",  "value": "适中",            "confidence": 0.6, "source": "dialogue" }
  ],
  "version": "v1",
  "updatedAt": "2026-06-15T10:00:00+08:00"
}
```
- 文档中需明确：本结构是**赛题要求的异质学生画像**，区别于既有 `GET /profile/ability-portrait` 返回的「6 知识点掌握度雷达」（后者保持不变，供 Dashboard）；二者并存、用途不同。
- `score` 仅「知识基础」等可量化维度有，其余维度可只有 `value`；`updatedAt` 体现「随学随新」（学习/测验后可更新对应维度）。

## 3) 新接口：获取学生画像  `GET /api/v1/profile/student-portrait`
- 响应 `data` 即上面的 StudentPortrait，供对话式诊断页右侧实时展示。
- 画像随对话/学习更新；本接口返回当前最新版本。

# 红线检查（完成后请逐条自检并报告）
1. 既有 30 个接口签名是否 100% 未改动？（特别是 `/profile/ability-portrait`）
2. 新接口是否套用统一信封 `{code, message, data, traceId}`？SSE/JSON 双模式是否都写清？
3. 是否未写任何实现代码、仅改了《后端接口文档.md》？

# 输出要求
1. 在《后端接口文档.md》合适位置新增章节（建议接在第 4 章 Profile 之后，编号与现有体例一致），并在末尾接口总览表追加 2 个新接口。
2. 结尾输出：本次新增/修改的文档章节清单 + 红线自检结果（逐条回答上面 3 点）。
3. 完成即停，不要顺手去写后端或前端代码——那是 C1-b / C1-c 两个独立会话的事。

═══════════════════════════════════════════════════════════════

## 给你（人）的几点提示

- 发之前，确认 Claude Code 的工作目录里能读到《后端接口文档.md》；如果它在某个子目录，指令开头补一句路径。
- CC 跑完后，**重点看它的红线自检第 1 条**——确认 `/profile/ability-portrait` 没被它"顺手优化"掉。
- 这一步产出的是契约。确认无误后，下一步（C1-b 后端会话）就让 CC 按这份契约实现对话式诊断 Agent + SSE；再下一步（C1-c 前端会话）改造 ProfileBuilder、复用 SocraticTutor 对话 UI、雷达图实时刷新。
- 如果 CC 提出更合理的字段命名或维度划分，可以采纳——契约阶段就是用来对齐的，定稿后再进实现。
