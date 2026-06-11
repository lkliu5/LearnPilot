# B7-b — 前端实时通道接入（Workflow WS / Tutor SSE / Video narration）· 完成总结

> 阶段：B7 后半（B7-b）｜状态：✅ 完成（0 报错）｜日期：2026-06-11
> 一句话：沿用联调 P0/P1 全部约定——`USE_REAL_API` 分支择一、mock 一行不删、
> 统一信封封装；UI 结构/样式/动效零改动（新增的「演示/实时」开关复用既有
> `workflow-btn` 样式与 PageHeader 徽章组件，未动任何 CSS）。

## 1. 交付内容

### ① AgentWorkflow：「演示 / 实时」模式开关（接口 27/28，文档 11 章）

- **开关**：页头操作区新增模式按钮（复用 `workflow-btn--secondary` 样式），仅
  `USE_REAL_API=true` 时渲染，默认「实时」；mock 模式恒为演示且无开关，行为与
  切换前逐帧一致。
- **演示模式**：既有 `simulateWorkflow` setTimeout 模拟链**原样保留**（评审断网
  兜底），一行未改。
- **实时模式**：`POST /workflow/execute` → `WS /api/v1/ws/workflow/{id}`。
  帧协议按 B7-a 约定消费：首帧全量、后续帧 `messages` 仅增量（按 id 去重追加）、
  `agents/stats/phase` 整帧替换——驱动既有 AgentStatusCard 指示灯 / 消息日志 /
  三项 stats（实时模式改吃帧内 `stats`）/ phase 指示器。
- **粒子流**：实时模式 GSAP MotionPath 粒子仅在 running 边流动（三条 Agent 边随
  对应节点 running 点亮，rag 边随生成节点）；演示模式保持全边流动不变。
  GSAP 时间线依赖增加 running 边集合 key，演示模式该 key 恒为 `''` 不触发额外重建。
- **自动回退**：execute 报错 / WS 连接失败 / 中途断开（complete 后的正常关闭除外）
  → 自动切回演示模式 + 页头「联调提示」徽章轻提示（4s 自动消失）+ 原模拟链接管，
  不白屏不报错；组件卸载 / 重置时主动断开 WS（不触发回退）。

### ② SocraticTutor：SSE 增量渲染（接口 22，文档 8.7 + 15.4）

- 联调分支走 `POST /resource/tutor/chat`（`Accept: text/event-stream`），
  **逐 delta 追加**到既有气泡（首个 delta 前沿用打字三点动画，样式未动）；
  `event: done` 后用返回的 `suggestions` 刷新快捷 chips（mock 模式 chips 恒为
  本地 quick，渲染零差异），`sessionId` 存 ref 供多轮会话保持。
- **失败回退**：SSE 连接失败 / `event: error` / 空流 → console.error + 回退本地
  关键词引导链（`branches`/`fallback` 一行未删）；已渲染片段按 15.4 约定保留。

### ③ VideoLecture：旁白脚本改吃 8.3（接口 18）

- 联调挂载时 `POST /resource/video`（difficulty 固定「初级」，与视频画面封面
  标注一致），`narration` 覆盖本地 `NARRATION`（services 层完成 `frame→from`
  字段映射，B7-a 第 5 节约定）；请求失败回退本地脚本。
- Web Speech 朗读、点击行 seek、字幕高亮行为不变（仅数据源换为 state，
  帧定位函数 `segIndexAt` 改为显式接收脚本参数）。

## 2. 文件清单

### 2.1 新增（4 个，≤8 上限）

| 文件 | 说明 |
|---|---|
| `frontend/src/services/workflow.ts` | 11.1 execute + 11.2 WS 订阅封装（信封校验、complete/失败/主动关闭三态区分） |
| `frontend/src/services/tutor.ts` | 15.4 SSE 解析（fetch + ReadableStream，EventSource 不支持 POST）；非流式信封错误（401/1004）解码抛 ApiError |
| `backend/scripts/verify_b7b.py` | 浏览器等价全链路实测（经 Vite 代理：WS 帧序列 / SSE 双轮 / video / 模块 transform），可重复回归 |
| `backend/scripts/verify_b7b_critic.py` | 强制 critic 低分 in-process 实测（钩子仅进程内可置），打印前端将消费的 error 帧序列 |

### 2.2 改动既有（5 个，均限「数据来源层」，UI/动效/结构/路由零改）

| 文件 | 改动点 | 理由 / 边界 |
|---|---|---|
| `frontend/vite.config.ts` | `/api` 代理追加 `ws: true` | 接口 28 的 WS 路径在 `/api/v1/ws/` 下，代理需支持 WebSocket 升级（原 `/ws` 代理条目保留未动）。**已运行的 dev server 需重启生效** |
| `src/pages/AgentWorkflow.tsx` | 新增 mode/liveStats/liveHint 状态 + `startLiveWorkflow`/`applyFrame`/`fallbackToDemo`；页头加开关按钮与提示徽章；stats 三处与粒子渲染按 mode 择一；`resetWorkflow` 补 WS 清理 | 既有 `simulateWorkflow`/`addMessage`/GSAP 测量与动效逻辑零改动；演示分支表达式取值与切换前逐项一致 |
| `src/components/SocraticTutor.tsx` | `send` 增 `USE_REAL_API` 分支走 `sendLive`（SSE）；chips 改 state（初值=本地 quick） | mock 分支（关键词引导链 + 700ms 模拟）一行未删；气泡/打字动画/输入区结构未动 |
| `src/components/VideoLecture.tsx` | 旁白脚本改 state（初值=本地 NARRATION），联调 effect 拉 8.3 覆盖；`segIndexAt` 显式接收脚本参数 | Remotion Player 参数仍用本地常量（durationInFrames/fps/宽高与后端回包一致，B7-a 已对齐）；TTS/seek/字幕行为不变 |
| `src/services/resource.ts` | 追加 `getVideo`（8.3，`narration[].frame→from` 映射）与 `VideoData`/`VideoNarrationLine` 类型 | 纯追加，既有函数未动 |

> 严格未触：路由 / Zustand store 结构 / CSS / framer-motion / GSAP 既有时间线逻辑 / 其余页面组件。

## 3. 启动 / 验证命令

```bash
# 后端（mock provider，无需任何 Key）
cd backend && python -m uvicorn app.main:app --port 8000

# 前端（.env 内 VITE_USE_REAL_API=true；vite.config 改动需重启 dev server）
cd frontend && npm run dev

# 全链路回归（VITE_PORT 为 dev server 实际端口）
cd backend && python scripts/verify_b7b.py
# 强制 critic 低分 error 帧（in-process）：
cd backend && python scripts/verify_b7b_critic.py
```

## 4. 实测结果（0 报错）

### ① 类型检查
```
npx tsc --noEmit -p tsconfig.json   →  EXIT 0（strict，演示/实时两分支均编译覆盖）
```

### ② 实时通道全链路（经 Vite 代理 :3004，浏览器等价路径，后端 mock）
```
[login]    code 0  via Vite proxy :3004
[execute]  code 0  workflowId=wf_8b07a1ddce26
[ws 帧1]   phase=diagnosis  step=1 progress=25  msgs(+0) | diagnosis:running generation:idle critic:idle
[ws 帧2]   phase=generation step=2 progress=50  msgs(+2) | diagnosis:success generation:running critic:idle
[ws 帧3]   phase=generation step=2 progress=50  msgs(+1) | diagnosis:success generation:running critic:idle
[ws 帧4]   phase=validation step=3 progress=75  msgs(+1) | diagnosis:success generation:success critic:running
[ws 帧5]   phase=validation step=3 progress=75  msgs(+1) | diagnosis:success generation:success critic:success
[ws 帧6]   phase=complete   step=4 progress=100 msgs(+1) | diagnosis:success generation:success critic:success
[ws]       6 帧经 Vite 代理收齐，消息 id 不重不漏（累计数 == 终帧 stats.messageCount）
[sse 轮1]  deltas=31 拼接前 18 字「好问题。先想一想：如果没有激活函数…」
[sse done] sessionId=s_cdd7ceadce suggestions=['等价于线性变换', '可以拟合任意函数', '不确定']
[sse 轮2]  deltas=49 会话保持 sessionId 一致=True
[video]    code 0  videoUrl=None narration=5 段 frames=[0, 90, 300, 540, 720] fps=30 1280x720 dur=900
[vite]     6 个改动模块 transform 200
ALL B7-B BROWSER-EQUIVALENT CHECKS PASSED (code 0)
```
> 帧1 即「节点随帧实时点亮」：diagnosis running 蓝灯 → 逐帧推进至全绿 complete；
> 消息日志按增量追加滚动；WS 经 `/api` 代理升级成功（vite `ws:true` 生效）。

### ③ 强制 critic 低分 → error 帧驱动红灯与重试过程（in-process，钩子仅进程内可置）
```
帧1   phase=diagnosis  step=1 | diagnosis:running generation:idle critic:idle
…
帧5   phase=generation step=2 | … critic:error  ⚠ 校验未通过（评分 0.42 < 阈值 0.8），发起第 1 次重试
帧7   phase=generation step=2 | … critic:error  ⚠ …发起第 2 次重试
帧9   phase=validation step=3 | … critic:error  ⚠ 校验仍未通过（评分 0.42），已达最大重试次数 2，触发降级输出
帧10  phase=complete   step=4 | diagnosis:success generation:success critic:error   ← 降级终态红灯保持
CRITIC-LOW CHECK PASSED: 10 帧，error 消息 3 条，critic 红灯帧 4 个，降级终态红灯保持
```
> 前端 `applyFrame` 对 error 帧无特殊分支——红灯由 `agents[].status` 数据直接驱动
> AgentStatusCard / 节点边框 / 状态点，error 消息按 `message-item--error` 既有样式渲染。

### ④ 停掉后端 → 回退条件成立
```
execute via proxy (backend down) -> HTTP 500
```
> 前端路径：`executeWorkflow` 解析失败抛 ApiError → `fallbackToDemo`：切回演示模式
> + 页头「已自动回退演示模式」轻提示 + 原模拟链接管。WS 中途断开走同一回退
> （`onclose` 触发 `onFail`；complete 后的正常关闭已置 settled 不触发）。

### ⑤ 开关关闭回归
`VITE_USE_REAL_API=false` 时：AgentWorkflow 无开关恒为演示模式（stats/粒子/启动
按钮全部回落原表达式与原文案「启动演示」）、SocraticTutor 走原 700ms 模拟链、
VideoLecture 旁白恒为本地 NARRATION——三处联调 effect/分支全部早返回，
行为与切换前逐帧一致；两分支均经 tsc 编译覆盖。

## 5. 诚实声明（未覆盖项）

- 同 P0/P1：本机无浏览器自动化工具，「真人点击走查 + 控制台 0 报错」未做自动化
  断言；已覆盖类型层（tsc 0 报错）、模块转译层（Vite transform 200）、契约层
  （WS 6 帧 / SSE 双轮 / video code 0）、代理层（HTTP + **WS 升级**均经 :3004 通）、
  回退条件层（后端停机 execute 500）。建议评审启动后手动走查：工作流大屏点
  「启动工作流」看节点随帧点亮 → 停后端再点看自动回退；资源页「苏格拉底导学」
  看流式打字 →「视频讲解」看旁白与字幕。
- 强制 critic 低分的红灯/重试过程：`set_force_critic_low` 为进程内测试钩子
  （B7-a 设计如此，无 HTTP 开关），故以 in-process WS 实收帧序列佐证——前端对
  error 帧无特殊分支，红灯由帧内 status 数据直接驱动，浏览器端渲染路径与 ② 的
  成功帧完全同源。
- 浏览器端 WS 中途断开（杀后端进程时机敏感）未在真实浏览器实测，回退逻辑经
  代码路径推演 + onclose/onFail 单一汇聚点保证（与 execute 失败走同一 `fallbackToDemo`）。

## 6. 给后续阶段的约定

- 至此接口文档 30 接口中前端可见链路已全部接通（18/22/27/28 为本阶段收口）；
  8.4 思维导图 / 8.5 Mermaid 仍按 P1 约定由讲义结构化 / 本地常量驱动，后端接口
  未实现（接口文档允许，列为可选增强）。
- `vite.config.ts` 的 `/api` 代理已支持 WS 升级；**改动前已在跑的 dev server
  需重启**才能走通实时模式（否则 WS 握手失败会触发演示回退——属预期兜底而非缺陷）。
- AgentWorkflow 实时模式 execute 当前发空体 `{}`（kpId 后端缺省 nn）；后续若需
  按 Journey 目标岗位触发，把 `executeWorkflow({ targetJobId })` 接 journey store
  即可，UI 无需改动。
