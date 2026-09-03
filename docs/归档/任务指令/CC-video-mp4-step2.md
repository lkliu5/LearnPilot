# CC 指令 · 第二步：讲解视频渲染成真 mp4（服务端 + 预渲染 + 资源库下载）

> 基于上一步环境探测（已跑通带音轨的最小 mp4 样例）的结论实现。把"画面 + edge-tts 旁白"烧录成一体 mp4，让讲解视频成为真视频、可下载。
> 全局纪律：已联调接口签名禁改（新增仅追加并同步文档）、统一信封、Mock/真实双模式（无 Key/无渲染能力时回落现有 Player+TTS、不破坏全链路）、复用优先、完成即停、tsc 干净 0 报错。

═══════════════════════════════════════════════════════════════

# 角色
资深全栈工程师。项目已联调，禁改既有接口签名。本会话把讲解视频服务端渲染成 mp4，沿用上一步探测确认的方案。

# 已探明的事实（直接用，不要推翻）
- @remotion/renderer + bundler + webpack 可装（--no-save 探测已成功）；compositor 自带 ffmpeg 能力，无需系统 ffmpeg。
- 无头浏览器：**复用本机已有的 Playwright chrome-headless-shell**，通过 browserExecutable 指过去，避开 googleapis 下载。
- 音轨：Remotion `<Audio>` + renderMedia 自动混音进同一 mp4，无需后期 ffmpeg。
- 段时长矛盾的解法：先对每段 narration 合成 edge-tts MP3 → 量出时长 → 把该段 Sequence 时长设为音频帧数 + 该段 `<Audio>`，画面与旁白精确同步。
- 渲染耗时 ~10–15s/视频，**不能放进请求**，必须预渲染 + 任务轮询。

# 任务

## 1. 后端视频渲染服务
- 新增 `app/services/video_render.py` + Node 渲染脚本（render.mjs，Python 经 subprocess 调用；renderer 是 Node 库）。
- 复用现有 8.3 的 scenes/narration，喂给现有 `LectureVideo` 组件渲染。
- **音频同步**：渲染前对每段 narration 调现有 edge-tts（services/tts）合成 MP3、量时长、设段时长、叠 `<Audio>`，画面与旁白精确对齐。
- **browserExecutable 固定指向复用的 headless shell**；bundle 产物（serveUrl）缓存复用、只 bundle 一次，后续只 renderMedia。

## 2. 预渲染 + 任务轮询机制（关键）
- 复用现有缓存/异步设施：POST /resource/video 命中 ResourceCache(kind=video) 且已有 mp4 → 直接回 videoUrl；否则起 taskId（pending→running→succeeded/failed），后台 bundle→合成各段TTS→renderMedia→落盘到静态目录→写回 videoUrl。
- 前端轮询任务状态（GET /tasks/{taskId} 或复用现有任务查询），succeeded 后用 videoUrl 播放/下载。
- mp4 落盘到可静态访问的目录、URL 可下载。

## 3. 前端：真视频播放 + 下载
- 视频有 mp4（videoUrl 非空）时：用原生 `<video>` 播放该 mp4（画面+旁白已烧录一体，不再是 Player+外挂 TTS）；
- 渲染中：显示"视频生成中…"进度/轮询态；
- **下载**：接入第一步的"我的资源库"——视频项从"即将支持"改为可下载该 mp4（把第一步留的占位接上）。

## 4. 降级纪律（重要）
- Mock 模式 / 无渲染能力 / 渲染失败时：videoUrl 仍可为 null，前端**回落现有 @remotion/player + edge-tts 实时播放**（即当前行为），不破坏"无 Key 全链路跑通"。
- 即：mp4 是增强，不是替换——拿不到 mp4 也要能看（实时播放器兜底）。

# 约束
- 依赖用 --save 正式装进 package.json（renderer/bundler/webpack）；不改既有接口签名（新增 video 渲染/任务查询为追加并同步文档）；复用现有 LectureVideo 组件 / tts / 缓存 / 任务设施；不破坏现有实时播放兜底。

# 验证（截图 + 实测）
1. 触发某知识点视频生成 → 后台渲染 → 得到 mp4：用 `<video>` 播放，**画面与旁白同步、是一体的真视频**（非幻灯+外挂音频）；
2. 预渲染：第二次访问同视频直接命中 mp4、秒出；渲染中有轮询态；
3. 下载：在"我的资源库"能下载该 mp4、文件正常可播放；
4. 降级：mock 模式 / 渲染不可用时，回落现有实时 Player+TTS、仍能看；
5. 既有链路无回归、全量测试通过、tsc 干净、0 console error。

# 输出
方案落地说明 + 改动文件清单 + 接口文档增量 + 5 项验证结果（含一个真实 mp4 的渲染耗时与播放确认）+ 红线自检。完成即停。

═══════════════════════════════════════════════════════════════

## 提示（给你人看）
- 这是重工程，CC 已探明路径，但实现里最容易出问题的是：① browserExecutable 路径要对（复用 Playwright 的 shell）；② 预渲染任务别阻塞请求；③ 降级兜底别丢（拿不到 mp4 要能回落实时播放）。验收死盯这三条。
- **渲染耗时 10-15s，演示前一定要预渲染**要演示的视频（像预热讲义那样），现场才秒出。
- 降级兜底是保命的——演示机如果渲染环境出问题，至少还能用现有实时播放器顶上。
