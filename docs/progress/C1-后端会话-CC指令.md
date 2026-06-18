# C1 第二步 · 后端会话 — Claude Code 指令

> 用法：把「═══」之间的全部内容复制发给 Claude Code。本会话**只写后端实现，按第 17 章契约**，不碰前端。

═══════════════════════════════════════════════════════════════

# 角色
你是资深后端工程师，正在为「软件杯·领域知识个性化资源生成与多智能体系统」实现「对话式学习画像诊断」后端。
项目已联调一轮，30+ 接口契约稳定；上一会话已在《后端接口文档.md》新增第 17 章对话式诊断契约。

# 契约权威
严格按《后端接口文档.md》**第 17 章**（17.1 `/profile/dialogue`、17.2 StudentPortrait 结构、17.3 `/profile/student-portrait`）实现，字段名逐字对齐。如与本指令有出入，以接口文档第 17 章为准。

# 本次任务范围
实现第 17 章的两个新接口及其支撑逻辑：
1. **对话式诊断 Agent**（如 `DialogueDiagnosticAgent`）：
   - 多轮追问策略：开放提问 → 针对回答追问 → 逐步定位知识基础/认知风格/易错点偏好/学习目标/先验经验/学习节奏。
   - 每轮从学生自然语言**抽取画像维度增量**，写入该用户的 StudentPortrait（随学随新，覆盖/累积更新对应维度）。
   - **防幻觉**：无法从对话判断的维度不编造；`source` 取 `dialogue|manual|inferred`，`inferred` 给低 confidence。
2. **`POST /api/v1/profile/dialogue`**：实现 SSE 流式（`delta` 追问 token → `event:portrait` 维度增量 → `event:done`；异常 `event:error`）与非流式 JSON 双模式，字段对齐 17.1；`sessionId` 会话上下文内存按 TTL 维持。
3. **`GET /api/v1/profile/student-portrait`**：返回该用户最新 StudentPortrait（含空画像约定，对齐 17.3）；提供 StudentPortrait 的持久化（可用现有 DB/SQLite，新增表或字段）。

# 复用与约束（重要）
- **复用现有 SSE 基建**：参照 8.7 苏格拉底辅导（15.4）已有的 `text/event-stream` 实现方式，沿用同一套流式封装，不要另造一套。
- **复用 `LLMClient` 适配层**：Agent 经 LLMClient 调模型，**Mock 与真实双模式**，无密钥可跑通；真实模式用现有默认模型即可（**无需接入讯飞星火**，已确认不强制）。
- **复用既有 Agent 基类 / 信封中间件 / traceId 注入**。
- **禁止修改任何已有接口的签名与实现**，尤其 `/profile/ability-portrait`（接口 7）——StudentPortrait 是新增并存结构，不要去动或合并知识点雷达。
- 新文件 ≤ 8 个，完成即停。

# 验证（请实测并在结尾贴结果）
1. curl 走多轮对话（非流式）：连续 3–4 轮，确认 `portraitUpdates` 逐轮累积、`/profile/student-portrait` 返回的维度随对话增多/更新。
2. SSE 模式：用 `curl -N -H "Accept: text/event-stream"` 验证 `delta` / `event:portrait` / `event:done` 事件序列正确。
3. Mock 与真实双模式各跑一遍，响应结构契约一致。
4. 回归确认：`/profile/ability-portrait` 与其他既有接口响应逐字未变。

# 输出要求
结尾输出：新增/修改文件清单 + 启动命令 + 上述 4 项验证的实测结果（curl/pytest 输出片段），0 报错才算完成。完成即停，**不要写前端**——前端改造是下一个独立会话（C1-c）。

═══════════════════════════════════════════════════════════════

## 给你（人）的提示
- 发前确认 CC 能读到《后端接口文档.md》第 17 章（即上一会话的产物已落盘）。
- 重点看验证第 1、4 条：①画像确实随对话累积更新（这是赛题"动态画像/随学随新"的硬证据，决赛要演示）；②既有接口零回归。
- 跑通后告诉我，下一步出 **C1-c 前端会话**：改造 ProfileBuilder 为对话式主路径、复用 SocraticTutor 对话 UI、右侧雷达图随对话实时刷新。
