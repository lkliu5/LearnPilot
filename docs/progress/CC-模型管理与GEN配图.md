# CC · 模型管理（界面切换模型 + 接入魔搭）+ Diffusion 板块论文级配图

> 完成日期：2026-07-07。两件事：① 模型注册表 + 界面切换生成模型 + 魔搭 ModelScope 接入（OpenAI 兼容）；
> ② GEN 生成式扩散板块 13 个知识点逐一精写论文级 Mermaid 图解 + Wikimedia 贴题门控扩充。
> **不改任何既有接口签名（新增仅追加）；默认模型 = 既有 DeepSeek，不切换则行为逐字不变。**

## 一、模型注册表 / 切换设计（含魔搭 OpenAI 兼容适配）

```
LLMClient（llm.py，25+ 语义方法，签名不变）
   └─ 真实路径统一改经 llm_transport.chat / chat_stream（调用形状与 llm_deepseek 逐字一致）
        ├─ 当前模型 provider=deepseek（默认）→ llm_deepseek（原通道，零变化）
        └─ 当前模型 provider=modelscope   → llm_modelscope（OpenAI SDK，base_url=魔搭 API-Inference）
              失败/超时/未配 Key → log 留痕后回落 llm_deepseek
              DeepSeek 亦不可用 → LLMGenerationError → 各方法既有 mock 兜底 / 路由 2001（绝不崩）
model_registry.py：注册表（现算自 settings）+「当前模型」进程内运行态
   - LLM_PROVIDER=mock → 注册表仅 [mock]（无 Key 全链路可跑纪律不变）
   - 否则 → [DeepSeek 默认] + MODELSCOPE_MODELS 清单（默认 GLM-4.6 / Qwen3-32B / DeepSeek-V3.1）
```

- **魔搭适配**：魔搭推理 API 兼容 OpenAI 协议——`llm_modelscope.py` 与 `llm_deepseek.py` 同构
  （OpenAI SDK + httpx 连接级重试 + 统一 LLMGenerationError），仅 base_url/Key/model 不同；
  model 由 transport 按注册表当前项逐次传入；Qwen3 非流式按官方口径 `enable_thinking:false`。
- **环境变量**（.env.example 已补样例）：`MODELSCOPE_API_KEY` / `MODELSCOPE_BASE_URL` / `MODELSCOPE_MODELS`。
- **新接口（接口文档新增 21 章 + 附录 45/46 行）**：
  - `GET /models`：注册表 + 当前模型（available 标记是否已配 Key；未配也可选，调用时自动回落）；
  - `PUT /models/current`：切换（未知 id → 1001/400）。均需登录、统一信封。
- **前端**：设置面板（侧边栏用户菜单 → 设置）新增「生成模型」区块——下拉切换 + 当前模型显示 +
  未配 Key 标注 + 降级说明文案；服务层新增 `services/models.ts`（USE_REAL_API=false 走本地演示数据）。

## 二、Diffusion（GEN）板块配图说明

- **论文级 Mermaid 模板 ×13**（`llm.py _DIAGRAM_TEMPLATES`，键 = kp_id，复用既有论文级样式：
  subgraph 分块 / `<br/>` 数学标注 / 虚线反馈边 / 图型按内容选择）：
  | kp | 图解 | | kp | 图解 |
  |---|---|---|---|---|
  | GEN-1 | 生成式模型谱系 mindmap | | GEN-8 | LDM 像素↔潜空间 pipeline |
  | GEN-2 | VAE 编码-重参数化-解码+双损失 | | GEN-9 | Stable Diffusion 文生图全管线（CLIP→去噪循环→VAE） |
  | GEN-3 | GAN 对抗博弈回路 | | GEN-10 | ControlNet 冻结主干+可训练副本+零卷积 |
  | GEN-4 | DDPM 前向加噪链+反向去噪链 | | GEN-11 | 加速采样三路线（DDIM/DPM-Solver/蒸馏） |
  | GEN-5 | 扩散数学推导链（闭式采样→ELBO→L_simple） | | GEN-12 | 视频/3D 扩散延伸 |
  | GEN-6 | U-Net 编码-瓶颈-解码+跳连 | | GEN-13 | 应用-风险-治理 mindmap |
  | GEN-7 | CFG 条件引导双路合成 | | | |
- **GEN 模板优先**（`generate_diagram`）：GEN-* 命中精写模板时真实模式也直接返回模板（质量确定性
  达标、不抽卡）；其余板块维持「真实生成优先、失败回落模板」原行为不动。
- **Wikimedia 贴题门控扩充**（`lecture_media.py _DOMAIN_RELEVANCE` 追加 7 条）：controlnet /
  stable diffusion·LDM / U-Net / VAE / GAN / 生成式模型 / 扩散（通配置底）；「diffusion」歧义极强，
  负词从严（osmosis/brownian/molecul/innovation/heat/physics…），无贴题图不强插（宁缺毋滥），
  防裂图兜底（onError 占位）不变。实测 GEN-9 命中 Commons 上的 Stable Diffusion 架构原图（MIT，带来源标注）。
- 已清除 GEN-* 旧 ResourceCache（7 行，升级前的泛化图解缓存），新图解即时生效。

## 三、改动文件清单

**后端（新增 5）**
- `backend/app/core/model_registry.py` — 模型注册表 + 当前模型运行态
- `backend/app/core/llm_modelscope.py` — 魔搭 OpenAI 兼容通道
- `backend/app/core/llm_transport.py` — 统一分发 + 优雅降级
- `backend/app/api/v1/models.py` — GET /models、PUT /models/current
- `backend/tests/test_model_registry.py` — 10 项契约测试

**后端（修改 5）**
- `backend/app/core/config.py` — modelscope_api_key / base_url / models 配置
- `backend/app/core/llm.py` — 真实调用点 llm_deepseek.* → llm_transport.*（签名不变）；GEN-1..13 论文级模板；GEN 模板优先
- `backend/app/core/lecture_media.py` — GEN 域贴题门控 7 条
- `backend/app/core/content_safety.py` — 模型级二次校验同走分发通道
- `backend/app/main.py` — 注册 models 路由；`backend/.env.example` — 魔搭样例

**前端（新增 1 / 修改 2）**
- `frontend/src/services/models.ts` — 模型注册表服务（新增）
- `frontend/src/components/Sidebar.tsx` / `Sidebar.css` — 设置面板「生成模型」区块

**文档**
- `docs/后端接口文档.md` — 新增 21 章 + 附录 45/46 行（additive）

## 四、验证结果（实测）

1. **pytest 全量**：`275 passed, 1 skipped`（含新增 10 项；1 skip 为既有跳过项）。
2. **tsc**：`npx tsc --noEmit` 0 错误。
3. **接口实测**（deepseek 模式，learner_001 token）：
   - `GET /models` → deepseek-chat(默认·isCurrent) + 3 个魔搭条目（available=false，未配 Key）；
   - `PUT /models/current {"modelId":"ZhipuAI/GLM-4.6"}` → current 切换成功；
   - `PUT` 未知 id → `{"code":1001,"message":"未知模型：nope/x"}` / 400；
   - `GET /resource/diagram/GEN-1..13` → 13 点全部命中精写模板（mindmap ×2 + flowchart ×11）。
4. **界面截图**（`docs/progress/img-CC-模型管理与GEN配图/`）：
   - `model-switch-1-default.png` 设置面板显示当前 DeepSeek + 下拉四模型；
   - `model-switch-2-glm.png` 切换后显示「当前：GLM-4.6（魔搭）」；
   - `gen9-sd-pipeline-mermaid.png` GEN-9 讲义内论文级 SD 全管线图解（去噪循环 subgraph）；
   - `gen9-wikimedia-image.png` Wikimedia 贴题真图（Stable Diffusion 架构原图，MIT 来源标注）；
   - `gen10-controlnet-mermaid2.png` GEN-10 ControlNet 双 subgraph + 零卷积图解；
   - `gen10-dark-theme.png` 主题切换下图解正常。
5. **优雅降级实测**：当前模型 = GLM-4.6（未配 Key）时生成 GEN-9 讲义——后端 log
   `魔搭模型 ZhipuAI/GLM-4.6 调用失败，回落默认 DeepSeek：MODELSCOPE_API_KEY 未配置…`，
   讲义正常产出（走 DeepSeek），页面无任何报错。
6. **0 console error**（本会话导航后 0 错误）；mermaid 渲染 0 失败（`.mermaid-error` 恒空）；无裂图
   （`.md-image-fallback` 0 个，Wikimedia 图 naturalWidth>0）。

## 五、红线自检

- ✅ 不改既有接口路径/字段/枚举：仅新增 `/models*`（接口文档 21 章 additive）；`/resource/lecture`
  等生成接口签名不变，模型选择是服务端运行态。
- ✅ Mock-first：`LLM_PROVIDER=mock` 时注册表仅内置 mock，无任何 Key 全链路可跑（pytest 基线即 mock，275 通过）。
- ✅ 稳健性：魔搭失败 → 回落 DeepSeek → 再回落 mock 兜底/2001，绝不崩（单测 + 实测 log 双证）。
- ✅ frontend/src 约束：本次按需求新增设置面板 UI（Sidebar.tsx/css）与 `services/models.ts`；
  未动任何业务逻辑 / Zustand store 结构 / 路由。
- ✅ 未重构已验收代码：llm.py 调用点仅模块名替换（签名/语义不变）；GEN 模板优先仅对 GEN-* 生效，
  nn/cnn 等既有板块行为不变（契约测试钉死项全部通过）。
- ⚠️ 说明：魔搭真实调用因本机未配 `MODELSCOPE_API_KEY` 未做在线实测（分发与回落路径已由
  monkeypatch 单测 + 实测降级 log 覆盖）；配 Key 后无需改码即可直连。

## 启动 / 验证命令

```bash
cd backend && python -m uvicorn app.main:app --port 8000   # 后端
cd frontend && npm run dev                                  # 前端（VITE_USE_REAL_API=true）
cd backend && pytest -q                                     # 275 passed, 1 skipped
cd frontend && npx tsc --noEmit                             # 0 错误
# 魔搭直连（可选）：backend/.env 追加 MODELSCOPE_API_KEY=ms-xxx 后重启
```
