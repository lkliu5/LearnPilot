# CC-video-mp4 第二步 · 讲解视频服务端渲染成真 mp4（完成总结）

把「画面 + edge-tts 旁白」烧录成一体 mp4，使讲解视频成为真视频、可下载；拿不到 mp4
时回落现有实时 Player + TTS。沿用上一步探测确认的方案（@remotion/renderer + bundler +
webpack、复用本机 Playwright chrome-headless-shell、`<Audio>` 自动混音、预渲染 + 任务轮询）。

## 方案落地

- **渲染链路**：`POST /resource/video/render` → 后台任务：各段 narration 调现有
  `services/tts`（edge-tts）合成 MP3 → `mutagen` 量时长 → 帧数写入 `scenes[].durationInFrames`
  → 音频以 `data:URI` 经 `inputProps` 传入（避免 staticFile/publicDir，使 bundle 产物可缓存复用）
  → Node 侧 `scripts/render-lecture.mjs` 用 `@remotion/renderer` `renderMedia` 把每段
  `SceneCard + <Audio>` 烧录成 h264+aac 一体 mp4 → 落盘静态目录 → 回写 8.3 `videoUrl`。
- **音画同步**：每段 Sequence 时长 = 该段音频帧数，`SceneCard` 淡出随之对齐（长旁白不被截断）。
- **bundle 一次**：`render-lecture.mjs` 首次 bundle 落 `data/video/bundle`，源（`src/remotion`）
  未变则后续直接以该目录作 serveUrl 跳过 bundle（实测二次渲染省去 ~12s bundle）。
- **browserExecutable**：自动探测复用 `%LOCALAPPDATA%/ms-playwright/chromium_headless_shell-*`，
  避开 googleapis 下载；无系统/后期 ffmpeg（compositor 自带）。
- **预渲染 + 轮询**：渲染 ~10-15s 不入请求；命中已渲染 mp4 → `ready` 秒出；进行中 → `rendering`
  + `taskId`，前端轮询 `GET /tasks/{taskId}`，`succeeded` 取 `result.videoUrl`。
- **降级纪律**：总开关关 / 无渲染能力 / Mock / 渲染失败 / 轮询超时 → `videoUrl` 维持 null，
  前端回落 `@remotion/player` + edge-tts 实时播放（原 8.3 行为），不破坏「无 Key 全链路跑通」。
- **子进程**：Node 渲染经 `asyncio.to_thread(subprocess.run)` 跑（不阻塞事件循环，且规避
  Windows SelectorEventLoop 不支持 asyncio 子进程的坑）。

## 改动文件清单

**后端（新增 2 / 改 5）**
- `app/services/video_render.py`（新）：能力探测、缓存命中、各段 TTS→时长→data:URI、Node 子进程、回写 videoUrl、任务去重。
- `app/api/v1/resource.py`：新增 `POST /resource/video/render`（追加，不改既有签名）。
- `app/schemas/resource.py`：新增 `VideoRenderRequest`。
- `app/core/config.py`：新增 `video_render_*` 配置（开关/目录/前端目录/浏览器/node/超时）。
- `app/main.py`：挂载 `StaticFiles` 于 `/api/v1/media/video`（复用前端 `/api` 代理）。
- `requirements.txt`：新增 `mutagen`（纯 Python，量 MP3 时长）。
- `tests/conftest.py`：测试基线强制 `video_render_enabled=False`（零网络/零子进程、确定性）。
- `tests/test_b7a.py`：新增 2 个用例（render 降级契约 + kp/难度错误码）。

**前端（新增 3 / 改 4）**
- `src/remotion/render/Root.tsx` + `index.ts`（新）：服务端渲染合成（变长段时长 + 各段 `<Audio>`，`calculateMetadata` 累加帧数）。
- `scripts/render-lecture.mjs`（新）：Node 渲染驱动（bundle 复用 + renderMedia + browserExecutable）。
- `src/remotion/LectureVideo.tsx`：导出 `SceneCard`/`C` + `SceneCard` 加可选 `dur`（**追加，实时 Player 行为不变**）。
- `src/services/resource.ts`：新增 `startVideoRender` / `getTaskStatus` + 类型。
- `src/components/VideoLecture.tsx`：mp4 就绪→原生 `<video>` 播放 + 下载；渲染中轮询态；无能力/失败→保持实时 Player 兜底。
- `src/components/VideoLecture.css`：mp4 播放器 / 下载按钮 / 渲染中横幅样式。
- `package.json`：`--save` 装入 `@remotion/{renderer,bundler,media-utils}`、`webpack`。

**文档**
- `docs/后端接口文档.md`：8.3 增量（videoUrl 命中回填）+ 8.3-r `POST /resource/video/render` + 总览表。

## 接口文档增量

见 `docs/后端接口文档.md` §8.3 增量 与 §8.3-r。要点：8.3 八字段口径不变，`videoUrl`
命中 mp4 时由 null 变 URL；新增 `POST /resource/video/render` → `{status, taskId, videoUrl}`。

## 5 项验证结果（截图 + 实测）

1. **真 mp4 · 画面与旁白同步一体**：触发 `nn/初级` 渲染 → 任务 `succeeded`，产物
   `getVideoMetadata` = **48.36s / 1280×720 / 30fps / video h264 + audio aac**（音轨已混入同一文件，非幻灯+外挂）。
   前端 `<video>` `readyState=4`、`videoWidth/Height=1280/720`、`duration=48.36`，正常播放。
   （另：2 场景自测 bundle 12.2s + render 9.1s = **22.4s**；5 场景整片任务端到端 ~47s 含全量 TTS+重 bundle。）
2. **预渲染秒出**：二次 `POST /resource/video` 直接回 `videoUrl`；再次 `POST /resource/video/render`
   返回 `status=ready`（**~2s**，无 taskId）；渲染中有 `rendering` 轮询态 + 进度（45→100）。
3. **下载**：`<video>` 下方「下载 mp4」按钮指向 `/api/v1/media/video/v_*.mp4`；静态 GET
   **200 / Content-Type video/mp4 / 3.45MB**，文件可正常播放。
4. **降级**：测试基线 `video_render_enabled=False` → `/resource/video/render` 回 `unavailable`
   且 `/resource/video.videoUrl` 维持 null（契约用例通过）；前端 mock 模式 / 无能力 / 失败 / 超时
   均保持现有实时 Player + TTS（代码路径 + 既有用例覆盖）。
5. **无回归**：`pytest -q` → **222 passed, 1 skipped**；前端 `tsc --noEmit` → **0 error**；
   浏览器 **0 console error**（唯一 warning 为既有 Remotion Player license 提示，与本次无关）。

## 红线自检

- [x] 既有接口签名未改：8.3 八字段与口径不变，渲染能力为**追加**端点（`/resource/video/render`）+ 静态挂载；契约快照 `_exact` 仍通过。
- [x] 统一信封：新端点经 `success/fail`，任务沿用 `tasks` 信封。
- [x] Mock / 无 Key / 无渲染能力全链路可跑：渲染是增强，缺任一能力→`unavailable`→实时 Player 兜底；测试零网络零子进程。
- [x] 复用优先：复用 `LectureVideo`（SceneCard 追加 `dur`）、`services/tts`、`ResourceCache`、`tasks` 设施。
- [x] 依赖正式入库：`@remotion/{renderer,bundler,media-utils}` + `webpack` 进 `package.json`；`mutagen` 进 `requirements.txt`。
- [x] 不破坏实时播放兜底；未重构已验收阶段代码；产物目录（`backend/data/video/*`）已被 `.gitignore` 覆盖。
- [x] 前端仅改数据获取层（`services/resource.ts`）+ 视频组件呈现，未动 store / 路由 / 业务逻辑。

## 启动 / 验证命令

```bash
# 后端（渲染默认开；缺能力自动降级）
cd backend && uvicorn app.main:app --reload --port 8000
cd backend && pytest -q                       # 222 passed, 1 skipped

# 前端（真实联调 + tsc）
cd frontend && set VITE_USE_REAL_API=true && npm run dev   # :3001
cd frontend && ./node_modules/.bin/tsc --noEmit            # 0 error

# 手动单测渲染（可选）：node scripts/render-lecture.mjs <cfg.json>
```

> 演示提示：渲染耗时 10-15s，演示前先对要展示的知识点触发一次渲染预热（像预热讲义那样），现场即秒出；演示机渲染环境异常时仍有实时 Player 兜底。
