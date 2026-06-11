# B7-a — P2 增强 + 实时通道（纯后端三件）· 完成总结

> 阶段：B7 前半（B7-a）｜状态：✅ 完成（0 报错）｜日期：2026-06-11
> 范围：① Workflow 接口（execute / 轮询 / WS 实时推送，消费 B5-a WorkflowTrace 与
> LangGraph 真实工作流）② SocraticTutor SSE 流式（15.4 格式，TTL 30 分钟会话）
> ③ Video（videoUrl:null + 5 段帧-旁白映射，对齐前端 LectureVideo）。
> 前端「演示/实时」开关与联调为 B7-b，本阶段未触碰 frontend/src。

## 1. 交付内容

### ① Workflow 实时通道（接口文档 11 章）

- **`POST /workflow/execute`**（11.1）：请求体 `{targetJobId?, kpId?}` 均可选
  （kpId 缺省 `nn`；targetJobId 经 JobSnapshot 解析岗位名，未知 → 1004）。
  预分配 `workflowId` 后**后台线程**跑 B5 的 `run_learning_workflow`（LangGraph
  真实工作流，线程自管 DB 会话），立即返回 `{workflowId}`。
- **`GET /workflow/{id}`**（11.2 轮询）：响应 data **严格 6 键**
  `workflowId/phase/step/agents[]/messages[]/stats`（pytest 断言无多余键）。
  运行中读内存最新快照；注册表淘汰（FIFO 200 条）/重启后兜底读 **WorkflowTrace
  持久化行**（B5-a 即按 11.2 渲染结构落库）；未知 id → 1004/404。
- **`WS /api/v1/ws/workflow/{id}`**：连接即先推**一帧全量快照**；之后节点进入/
  退出/重试/降级时推**同结构增量帧**（`messages` 仅含新增、按 id 截断去重，
  agents/stats/phase 为当前全量）；每帧套统一信封 `{code,message,data,traceId}`；
  complete 帧后服务端正常关闭；未知 id → 信封 `code 1004` 帧后关闭。
- **实时观察点**：`run_learning_workflow` 增补 `workflow_id` / `on_update` 参数，
  `invoke()` 改为 `stream(stream_mode="values")` 逐节点产出累积 State（终态与
  invoke 等价，**拓扑 / trace 结构 / 返回值不变**，B5 测试全绿无回归）。
  快照状态机：`diagnostic→(generation,2) / generation→(validation,3) /
  validation[retry]→(generation,2)重试帧 / decision→(complete,4)`；
  critic 校验未通过即红灯（`error`），降级终态红灯保持——驱动 AgentStatusCard。
- **演示节奏**：`WORKFLOW_STEP_DELAY_MS`（默认 500，测试置 0）控制节点间推进
  延迟，mock 毫秒级工作流也能在大屏/轮询观察到 phase 渐进。

### ② SocraticTutor（接口文档 8.7 + 15.4）

- **`POST /resource/tutor/chat`** 双模式：不带 `Accept: text/event-stream` →
  8.7 整体 JSON `{sessionId, reply, suggestions}`；带该头 → 15.4 SSE：
  `data:{"delta":..}` 逐条（空行分隔）→ `event: done`（携带 sessionId +
  suggestions）；生成异常 → `event: error {code:2001,...}`（已发 delta 前端保留）。
- **会话上下文**：进程内存 dict + **TTL 30 分钟**（访问续期、惰性清理）；
  过期/未知 sessionId → 以该 id 重建空上下文。生产替换 Redis，写 README。
- **mock**：确定性引导链（关键词分支，首分支与 8.7 文档示例逐字一致）
  **逐字流式**（`TUTOR_STREAM_DELAY_MS` 打字机效果）；引导链覆盖
  「加权求和→偏置→非线性→ReLU→反向传播」闭环，与前端 SocraticTutor 演示对齐。
- **deepseek**：`llm_deepseek.chat_stream`（OpenAI 兼容 `stream=True`）真实
  逐 chunk 透传，system prompt 约束**「只用引导式提问启发，绝对不直接给出最终
  答案，以问题收尾」**；多轮 history 注入（`chat`/`chat_stream` 增加 history
  参数，向后兼容）；流中断/空流统一 LLMGenerationError → `event: error` 2001。

### ③ Video（接口文档 8.3）

- **`POST /resource/video`**：`{kpId, difficulty}` → `videoUrl: null`（走前端
  Remotion Player + TTS；服务端渲染 mp4 为可选加分项，生产路径写注释）+
  `narration[]` **5 段帧-旁白映射**（起始帧 `0/90/300/540/720` 与前端
  LectureVideo 5 个 Sequence 场景一致；nn 旁白与组件 NARRATION 逐字一致，
  其余知识点同结构模板化）+ `fps:30 / width:1280 / height:720 /
  durationInFrames:900`（与 Remotion 组件常量一致）。
  未知 kp → 1004；难度档非法 → 1001。

## 2. 文件清单

新增 4 个（≤8 上限）：

| 文件 | 说明 |
|---|---|
| `backend/app/services/workflow_runner.py` | 后台运行注册表 + 11.2 快照组装 + WS 订阅发布（跨线程经 `call_soon_threadsafe`） |
| `backend/app/api/v1/workflow.py` | 11.1 execute + 11.2 轮询 + WS 推送（execute 请求体 model 内联本文件） |
| `backend/app/services/tutor.py` | TTL 30min 会话 + 8.7 JSON / 15.4 SSE 事件流 |
| `backend/tests/test_b7a.py` | 15 条契约测试（TDD：先 RED 再实现转绿） |

既有文件改动：

| 文件 | 改动 | 既有行为影响 |
|---|---|---|
| `app/workflows/learning_workflow.py` | 增 `workflow_id`/`on_update` 可选参数；invoke→stream(values) | 无（B5 用例全绿） |
| `app/core/llm.py` | 追加 tutor 引导链 + `tutor_chat`/`tutor_chat_stream`/`tutor_suggestions` | 无 |
| `app/core/llm_deepseek.py` | `chat` 增可选 history；新增 `chat_stream` | 无 |
| `app/api/v1/resource.py` | 追加 `/resource/video`、`/resource/tutor/chat` 路由 | 无 |
| `app/services/resource.py` | 追加 `generate_video`（确定性，无缓存） | 无 |
| `app/schemas/resource.py` | 追加 `VideoRequest` / `TutorChatRequest` | 无 |
| `app/core/config.py` | 追加 `workflow_step_delay_ms` / `tutor_stream_delay_ms` | 无 |
| `app/main.py` | 挂载 workflow 路由 | 无 |

## 3. 启动 / 验证命令

```bash
cd backend && uvicorn app.main:app --reload --port 8000
cd backend && python -m pytest tests/ -q          # 注意 ↓「环境注记」
# WS 演示（任意 websocket 客户端）：
#   POST /api/v1/workflow/execute → ws://localhost:8000/api/v1/ws/workflow/{workflowId}
# SSE 演示：
#   curl -N -X POST .../api/v1/resource/tutor/chat -H "Accept: text/event-stream" \
#     -H "Authorization: Bearer <token>" --data-binary @body.json
```

## 4. 验证实测（0 报错）

### ① pytest（TDD：先 RED——`app.services.tutor` ImportError，实现后全绿）

```
$ JOB_MARKET_OFFLINE=false python -m pytest tests/ -q
70 passed, 1 skipped in 38.78s    （15 条 B7-a 新增 + 55 条既有，全绿）
```

15 条新增：execute→轮询严格 11.2 六键 / 默认体与 401 / 未知 id 1004 /
注册表淘汰后兜底 WorkflowTrace 行 / WS 全量+增量帧（信封+消息 id 不重不漏）/
强制低分 WS error 消息+重试帧+critic 红灯 / WS 未知 id 信封 1004 /
tutor JSON+会话保持 / 未知 kp 1004 / TTL 过期重建 / SSE mock 逐字+done /
SSE deepseek 真实流式（monkeypatch 断言 system 含「引导」「不直接给」）/
SSE error 事件 2001 / video 契约（帧位+参数与 LectureVideo 对齐）/ video 异常码。

### ② curl 触发 execute → 轮询 phase 推进（mock，步进延迟 1.2s，0.4s 轮询）

```
POST /workflow/execute → {"code":0,"data":{"workflowId":"wf_a7d465d66c9f"},...}
phase=diagnosis   step=1 progress=25  completed=0 msgs=0 | diagnosis:running generation:idle critic:idle
phase=generation  step=2 progress=50  completed=1 msgs=3 | diagnosis:success generation:running critic:idle
phase=validation  step=3 progress=75  completed=3 msgs=5 | diagnosis:success generation:success critic:success
phase=complete    step=4 progress=100 completed=3 msgs=6 | diagnosis:success generation:success critic:success
```

### ③ python websockets 客户端实收帧序列（happy path，5 帧）

```
帧1(全量快照) phase=generation step=2 progress=50 | diagnosis:success generation:running critic:idle
      msgs: #1[request] 用户→学情诊断Agent: 发起「神经网络基础」…; #2[response] 学情诊断Agent→…
帧2(增量) phase=generation step=2 | msgs: #3[response] RAG系统→领域知识生成Agent: 检索到 3 条…
帧3(增量) phase=validation step=3 | diagnosis:success generation:success critic:running
帧4(增量) phase=validation step=3 | msgs: #5[response] …校验通过（评分 0.93，幻觉率 0.021）
帧5(增量) phase=complete   step=4 progress=100 | msgs: #6[response] …学习资源已交付
-- 服务端正常关闭，共实收 5 帧 --
```

### ④ 强制 critic 低分（set_force_critic_low 钩子，in-process 服务端）→ error + 重试帧

```
帧2(增量) phase=validation | critic:running   msgs: #4[request] …（首次）请校验
帧3(增量) phase=generation | generation:running critic:error      ← 重试帧（红灯）
      msgs: #5[error] 校验未通过（评分 0.42 < 阈值 0.8），发起第 1 次重试
帧5(增量) phase=generation | generation:running critic:error
      msgs: #7[error] …发起第 2 次重试
帧7(增量) phase=validation | critic:error
      msgs: #9[error] …已达最大重试次数 2，触发降级输出
帧8(增量) phase=complete progress=100 | critic:error（降级红灯保持）
      msgs: #10[response] 已降级交付（validationScore=0.42，待人工复核）
-- 共实收 8 帧 --
```

### ⑤ SSE 双模式（curl -N 实测）

mock（逐字流式 + done）：
```
data: {"delta": "好"}
data: {"delta": "问"}
data: {"delta": "题"}
…
event: done
data: {"sessionId": "s_dfce5f9abe", "suggestions": ["等价于线性变换", "可以拟合任意函数", "不确定"]}
```

deepseek（真实 Key，29 个流式事件，引导式提问收尾不给答案）：
```
data: {"delta": "想象"}
data: {"delta": "一下"}
data: {"delta": "，"}
…
event: done
data: {"sessionId": "s_42af795ce2", "suggestions": []}
拼接回复: 想象一下，如果神经网络里只有线性变换（比如 y=wx+b），多层叠加后能表达什么？这和单层有什么区别？
```

JSON 模式（同接口不带 Accept 头，向后兼容 8.7）：
```
{"code":0,"data":{"sessionId":"s_a6e028b768","reply":"好问题。先想一想：如果没有
激活函数，多层网络叠加后等价于什么？","suggestions":[…]},…}
```

### ⑥ Video（curl 实测，nn 旁白与前端逐字一致）

```
{"videoUrl":null,"narration":[{"frame":0,"text":"欢迎学习神经网络基础。…"},
 {"frame":90,…},{"frame":300,…},{"frame":540,…},{"frame":720,…}],
 "fps":30,"width":1280,"height":720,"durationInFrames":900}
```

## 5. 环境注记 / 给 B7-b 的约定

- **跑测试需 `JOB_MARKET_OFFLINE=false`**：开发 `.env` 故意置 true 演示 5.2
  离线降级（code 2002），B6 用例按在线契约断言——环境开关问题，非代码缺陷。
- 开发库曾遗留多难度 `lecture@deepseek` 缓存行使 B5-b 一条用例
  `one_or_none()` 报 MultipleResultsFound（联调真实生成产生的脏数据，**先于
  本阶段存在**），已清理缓存行（可再生数据），未改任何已验收代码。
- WS 鉴权：契约 11.2 未定义 WS 凭据传递，本阶段 WS 不强制 token（execute /
  GET 均需登录，workflowId 不可枚举）；B7-b 联调若需可加 `?token=` 校验。
- 帧协议（B7-b 前端消费）：首帧全量、后续帧 `messages` 仅增量，agents/stats/
  phase 始终全量——前端可整帧替换状态、messages 做追加渲染。
- 视频参数 1280×720 取自前端 Remotion 组件实参（接口文档 8.3 示例 1920×1080
  仅为示例值，字段名未变）；`narration[].frame` 字段名按接口文档（前端组件内
  常量名为 `from`，B7-b 接线时由前端 services 层映射）。
- mock 全链路无 Key 可跑（execute→WS / SSE / video 实测均在
  `LLM_PROVIDER=mock` 完成）；deepseek 仅 tutor SSE 走新增 `chat_stream`，
  工作流/讲义链路未动。
