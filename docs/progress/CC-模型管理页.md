# CC 会话 · 模型管理独立页（界面配 Key + 多模型切换 + 安全）完成总结

> 依据 `docs/归档/任务指令/CC-model-management-page.md`。把模型管理从「设置里选」升级为左侧工具栏独立功能页：
> 用户可界面配置多个模型接入（含 API Key）、测试连通、一键切换；key 加密存储 / 脱敏回显 /
> 按 user 隔离，为产品化打底。既有接口签名零改动（全部 additive）。

## 一、设计要点

### 1. 双层「当前模型」（向后兼容 + 按用户隔离）

- **内置模型**（.env 驱动：默认 DeepSeek + 魔搭清单）切换 → 维持既有 §21.2 进程级运行态语义，
  行为与本功能上线前逐字一致（`test_model_registry.py` 全部原样通过）。
- **用户自建配置**（新增 `user_model_configs` 表）设为当前 → 仅写该用户的 overlay
  （`user_model_choices` 表，持久化、重启不丢），**只对本人生效**——A 的 key 绝不会被 B 的生成使用。
- 解析顺序（`model_registry.current()`）：上下文用户 overlay（有效）→ 进程级运行态 → 默认首项。
  默认行为不变（当前模型默认 = DeepSeek；mock 模式仅 mock）。

### 2. 用户身份注入（生成接口签名零改动）

- HTTP：`UserContextMiddleware`（security.py）best-effort 解 JWT `sub` → contextvar 绑定；
  与 envelope.TraceIdMiddleware 同机制，请求派生的 asyncio 任务自动继承。
- 工作流后台线程（唯一的 raw Thread 生成路径）：`workflow_runner._worker` 已有 `user_id`
  入参，起跑时显式 `model_registry.bind_user(user_id)`。
- 24 处 `llm_transport.chat/chat_stream` 调用点**零修改**。

### 3. key 安全（三条红线）

| 红线 | 实现 |
|---|---|
| 加密存储 | `app/core/crypto.py`：Fernet（cryptography 库）；密钥材料 `MODEL_KEY_SECRET`（缺省从 `JWT_SECRET` SHA-256 派生，零配置可跑、重启可解）。DB 只存 Fernet token + last4，无明文。 |
| 脱敏回显 | 所有响应只含 `apiKeyMasked`（`****`+后四位）；编辑表单不回填明文（留空=保留原 key）。 |
| 日志/错误 | 上游异常串统一 `crypto.redact()` 清洗后才抛/打日志；`PiiMaskingFilter` 追加 `sk-/ms-` 令牌形态兜底掩码；前端 key 仅存在于表单瞬时 state，提交/关闭即弃（不进 localStorage / 持久化 store，实测存储无 key）。 |

隔离：任何按 id 读写先校验 `user_id` 归属，非本人一律 `1004/404`（不泄露存在性）。

### 4. 稳健与降级链

自建模型失败/超时（`llm_userconf` 收敛 LLMGenerationError）→ **回落默认 DeepSeek** →
仍失败 → 各生成方法既有 mock 兜底 / `code 2001`，绝不崩。流式：未产出内容前失败可回落，
已产出后中断按既有 SSE error 兜底（不静默截断）。`LLM_PROVIDER=mock` 无任何 Key 全链路可跑
（286 项 pytest 全部在 mock 基线通过）。

## 二、改动文件清单

**后端（新增 4 文件，修改 10 文件）**

| 文件 | 内容 |
|---|---|
| `app/core/crypto.py` 新增 | Fernet 加密/解密/mask/redact |
| `app/core/llm_userconf.py` 新增 | 自建配置 OpenAI 兼容调用通道 + probe 连通性测试（key 全程脱敏） |
| `app/services/model_configs.py` 新增 | CRUD/归属校验/overlay 切换/测试目标解析（领域错误 → 信封） |
| `tests/test_model_configs.py` 新增 | 13 项契约测试（CRUD/加密/脱敏/隔离/per-user/降级/probe/日志红线） |
| `app/models/entities.py` | +`UserModelConfig` / `UserModelChoice` 两表（create_all 自动建，无迁移） |
| `app/core/model_registry.py` | ModelSpec +`source`/`api_key`；contextvar bind_user；`current()` overlay 解析；`user_snapshot()` |
| `app/core/llm_transport.py` | chat/chat_stream 增自建分支（失败回落默认 DeepSeek） |
| `app/api/v1/models.py` | +POST/PUT/DELETE `/models/configs`、POST `/models/configs/test`；GET/PUT 既有两接口签名不变（响应 additive 扩展 + per-user 语义） |
| `app/core/security.py` | +`UserContextMiddleware`（不改鉴权语义） |
| `app/main.py` | 注册 UserContextMiddleware |
| `app/services/workflow_runner.py` | `_worker` 起跑绑定发起用户 |
| `app/core/config.py` | +`model_key_secret` / `model_test_timeout_seconds` |
| `app/core/logging.py` | PiiMaskingFilter +API Key 形态掩码 |
| `requirements.txt` | +cryptography |

**前端（新增 2 文件，修改 3 文件；均为 CLAUDE.md 允许的 additive 页面接入模式，业务逻辑/store/既有路由未动）**

| 文件 | 内容 |
|---|---|
| `src/pages/ModelManagement.tsx` / `.css` 新增 | 独立页：列表卡片（状态 chips）/添加·编辑弹窗/测试连通/两步删除/toast；token 化样式深浅主题自适配 |
| `src/App.tsx` | PageType +`'model-management'`、import、renderPage case（additive） |
| `src/components/Sidebar.tsx` | 「工具」组 +模型管理入口 + 图标（既有设置下拉逐字未动） |
| `src/services/models.ts` | 类型 additive 扩展 + add/update/delete/test 四函数（含 mock 分支，key 不留存） |

**文档**：`docs/后端接口文档.md` §21 追加 21.3（CRUD）/21.4（测试连通）/21.5（运行语义）+
21.2 per-user 语义注记；既有 21.1/21.2 定义逐字未改。

## 三、启动与验证命令

```bash
cd backend && uvicorn app.main:app --port 8000     # 后端
cd frontend && npm run dev                         # 前端 :3001
cd backend && pytest -q                            # 286 passed, 1 skipped（含新增 13 项）
cd frontend && npx tsc --noEmit                    # 0 报错
```

## 四、实测结果（2026-07-07，LLM_PROVIDER=deepseek 真实模式）

- `pytest -q` → **286 passed, 1 skipped**（新增 test_model_configs.py 13 项全过；既有
  test_model_registry.py 8 项原样通过 = 内置切换行为无回归）。
- `npx tsc --noEmit` → 0 输出（干净）。
- 页面浏览器实测（截图见 `docs/progress/img-model-management/`）：
  - `mm-01` 侧栏「工具」组模型管理入口 + 独立页；
  - `mm-02` 编辑弹窗「测试连通」→ ✅ 连接成功（831ms），模型回复 OK（自配 DeepSeek Key，
    走 llm_userconf 用户 key 通道）；key 输入框仅显示「留空保留原 Key（****8a9a）」；
  - `mm-03` 界面添加魔搭模型（provider 选魔搭自动预填 base_url + 填 key + model_id）；
  - `mm-04` 无效 key 测试 → ❌ 连接失败（401），错误信息**不含 key**；
  - `mm-05` 列表：4 内置 + 2 自建，当前使用/可用/未配 Key 状态、key 一律 ****后四位；
  - `mm-06` 一键切换到魔搭自建配置 → 「当前使用」即时迁移；
  - `mm-07` 墨纸（ink）主题正常（`data-theme=ink` 实测生效）；
  - `mm-08` 既有设置下拉兼容：内置+自建同源展示、选中态正确（无回归）。
- 安全实测：
  - DB：`user_model_configs.api_key_encrypted` 为 `gAAAAAB...` Fernet token，
    `plaintext_in_db=False`；
  - 前端 localStorage/sessionStorage 扫描：无任何 key 痕迹；
  - 后端运行日志：完整 key（真/假）均未出现；降级日志「自建模型 umc_58df… 调用失败，
    回落默认 DeepSeek」留痕（错误串已脱敏）；
  - A/B 隔离：B 的 GET /models 看不到 A 配置（0 条）；B 对 A 配置 PUT/DELETE/test → 404；
    A 切自建后 B 与无上下文 `current()` 仍为 deepseek-chat。
- 稳健实测：当前模型=无效 key 自建配置时调用 `/resource/tutor/suggest` → HTTP 200 契约数据
  （优雅回落默认 DeepSeek，不崩）；换回有效自建配置 → 正常生成。
- 浏览器 console：本会话导航后 **0 error**（仅 1 条既有 THREE.js 弃用 warning，非本次引入）。

## 五、红线自检

- [x] 既有接口签名零改动（GET /models、PUT /models/current 路径/字段/枚举逐字不变；新增全部 additive 并同步文档）
- [x] 统一信封 `{code,message,data,traceId}` + 错误码对齐 1.3（1001/1004/2001）
- [x] Mock-first：无任何 Key 全链路可跑（conftest mock 基线 286 项全过；mock 模式注册表仅 mock）
- [x] 默认行为不变：不切换即 DeepSeek；内置切换语义与上线前逐字一致
- [x] key 加密存储（Fernet）/ 脱敏回显（****后四位）/ 不进日志与错误信息 / 前端零留存
- [x] 按 user 隔离（归属校验 + per-user overlay + 404 不泄露存在性）
- [x] 失败优雅降级绝不崩（自建 → 默认 DeepSeek → mock/2001 三级兜底，实测通过）
- [x] 轻量栈不变（仍 SQLite/Chroma；新表 create_all 自动建，无迁移工具）
- [x] frontend/src 改动仅为 additive 页面接入（App.tsx 路由 case / Sidebar 入口 / services 层 / 新页面），业务逻辑与 store 未动
- [x] tsc 干净 / pytest 0 失败 / 0 console error / 深浅主题正常

## 六、生产化注记（README 口径，本次不实现）

- `MODEL_KEY_SECRET` 生产必须配置专用随机串（缺省 jwt_secret 派生仅 demo 兜底）；
- 密钥轮换：更换 MODEL_KEY_SECRET 后旧密文解不出 → 按「未配 Key」降级，用户重填即可（不崩）；
- 客户端分离 / key 本地存储为未来产品化方向（答辩展望），本架构（配置即数据行 + 通道即
  base_url/key 参数化）可直接平移。
