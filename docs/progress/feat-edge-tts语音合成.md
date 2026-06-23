# feat：edge-tts 语音合成服务（讲解视频/导学旁白配音升级）

## 现状说明

- 改动前：讲解视频（`VideoLecture.tsx`）与导学旁白用浏览器自带 `speechSynthesis`（机械音），
  后端无任何 TTS 能力。
- 改动后：后端新增 edge-tts 神经语音合成服务（默认 `zh-CN-XiaoyiNeural`，语速 -10%、音调 +2Hz），
  统一供前端调用。**Web 模式**：后端只做"文字 → MP3 字节流"，由前端播放——不移植桌面端的
  pygame 播放 / 状态机 / 队列 / 优先级逻辑。既有 30+ 接口签名零改动，本接口为 additive。

## 改动文件清单

**新增（3）**
- `backend/app/services/tts.py` —— edge-tts 合成核心：`Communicate(...).stream()` 收集 audio
  分片合并为 MP3 bytes；3 次重试兜底（`TTS_MAX_RETRIES`）；md5(text|voice|rate|pitch) 缓存到
  本地目录命中即返回；`tts_provider=none`/合成多次失败 → 抛 `TTSUnavailable`（上层降级）。
- `backend/app/api/v1/tts.py` —— `POST /tts/synthesize`：成功直接返回 `audio/mpeg` 流
  （`X-TTS-Cache`/`X-TTS-Voice` 头），失败/禁用套统一信封 `code 2002 / data.offline=true`（HTTP 200）。
- `backend/tests/test_tts.py` —— 7 个用例：登录校验/空文本 1001/MP3 流/缓存命中/provider=none
  降级/重试后降级/缓存键稳定性（monkeypatch 合成函数，不依赖联网）。

**修改（5）**
- `backend/app/core/config.py` —— 新增 `tts_provider/tts_voice/tts_rate/tts_pitch/tts_cache_dir/
  tts_timeout_seconds/tts_max_retries/tts_max_chars` 配置（均带默认值，无 .env 可跑）。
- `backend/app/schemas/resource.py` —— 新增 `TTSSynthesizeRequest`（text + 可空 voice/rate/pitch）。
- `backend/app/main.py` —— 挂载 `tts.router`。
- `backend/requirements.txt` —— 追加 `edge-tts`。
- `.gitignore` —— 追加 TTS MP3 缓存目录（`backend/data/tts_cache/`，本就被 `backend/data/` 覆盖，显式标注）。

## 配置开关

| 配置（.env） | 默认 | 说明 |
|---|---|---|
| `TTS_PROVIDER` | `edge` | `edge`（edge-tts 联网免密钥）/ `none`（禁用 → 降级） |
| `TTS_VOICE` | `zh-CN-XiaoyiNeural` | 音色 |
| `TTS_RATE` / `TTS_PITCH` | `-10%` / `+2Hz` | 语速 / 音调 |
| `TTS_CACHE_DIR` | `./data/tts_cache` | MP3 缓存目录（已 gitignore） |
| `TTS_TIMEOUT_SECONDS` / `TTS_MAX_RETRIES` | `20.0` / `3` | 单次超时 / 重试次数 |
| `TTS_MAX_CHARS` | `2000` | 单次文本上限（超出截断） |

## 接口文档增量

`docs/后端接口文档.md` §8.9（additive）：`POST /api/v1/tts/synthesize`，请求 `{text, voice?, rate?, pitch?}`，
成功返 `audio/mpeg` 流，降级返 `code 2002 / data.offline=true`。详见文档。

## 启动 / 验证命令

```bash
cd backend && uvicorn app.main:app --reload --port 8000
cd backend && pytest -q tests/test_tts.py      # TTS 专项
cd backend && pytest -q                          # 全量回归
```

## 验证结果（实测）

1. **专项 + 全量测试通过**
   - `pytest tests/test_tts.py` → `7 passed`
   - `pytest -q`（全量）→ `203 passed, 1 skipped`（既有接口零回归）

2. **真实合成（联网）+ 缓存提速**（`app.services.tts.synthesize` 直调）
   ```
   1st bytes=28080 from_cache=False 4.26s
   2nd bytes=28080 from_cache=True  0.000s
   MP3 frame sync (0xFF Fx)：True（首字节 fff364c4 = MPEG1 Layer3）
   ```

3. **接口实测（curl，登录后）**
   - 成功：`HTTP 200` / `Content-Type: audio/mpeg` / `X-TTS-Cache: miss` / `X-TTS-Voice: zh-CN-XiaoyiNeural`，
     落盘 39600 字节、head4 `fff364c4`（合法 MP3）；第二次同文本 `X-TTS-Cache: hit`。
   - 空文本：`{"code":1001,"message":"合成文本不能为空"}`。
   - 未登录：`401`。

4. **优雅降级（不崩）**
   - `tts_provider=none` → `HTTP 200 / code 2002 / data.offline=true`（test_provider_none_degrades）。
   - 模拟断网（合成抛异常）→ 重试 3 次后 `code 2002 / offline=true`（test_edge_failure_degrades_after_retries）。
   - 前端按 `Content-Type` 判别：非 `audio/mpeg` 即回落浏览器 speechSynthesis。

## 红线自检（CLAUDE.md）

- ✅ 统一信封：降级/错误走 `{code,message,data,traceId}`；成功为二进制流（接口文档已显式声明音频流口径）。
- ✅ Mock-first / 无密钥可跑：edge-tts 免密钥；`TTS_PROVIDER=none` 或无网时降级不崩，全量测试不依赖联网。
- ✅ 未改既有接口签名/字段/枚举；本接口 additive，文档追加 §8.9。
- ✅ 未引入重型依赖（仅 edge-tts，纯 Python）；未碰 frontend/src 业务逻辑。
- ✅ 缓存目录入 .gitignore；运行时产物未入库（git status 确认 backend/data 被忽略）。
- ✅ 新增文件 3 个（≤8）；完成即停，未顺手改前端组件。

## 前端接入提示（本次未改前端，留待联调）

`VideoLecture.tsx` 的 `speak()` 可改为：`fetch('/api/v1/tts/synthesize', {POST, text})` →
若 `Content-Type=audio/mpeg` 则 `new Audio(URL.createObjectURL(await res.blob())).play()`；
否则（降级信封）回落现有 `speechSynthesis`。此改动属 `src/services/` 数据获取层，需单独评审。
