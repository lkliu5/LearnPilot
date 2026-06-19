# CC 批3-C — 资源推荐升级为 AI 联网搜索聚合（问题 7）

> 把"资源推荐"从静态种子库改为 **AI 联网搜索聚合**：可插拔搜索 provider + 聚合/审核 Agent
> 评分；无搜索能力时 mock/种子兜底可跑。不改既有接口签名（新增仅追加）。

═══════════════════════════════════════════════════════════════

## 现状说明（修复前）
- `GET /resource/external/{kpId}` → `resource.external_resources` 读 **静态 `ExternalResource`
  种子表**（init_db `_EXTERNAL_RESOURCES`，每核心 KP 3-4 条人工精选），**无联网搜索**。
- 前端 `ResourceAggregator` 直接渲染该静态清单。

## 搜索能力确认
- 当前**未配置任何联网搜索 API**（config 无 search_* 项）。
- 已把搜索源**抽象成可插拔 `SearchProvider` 接口 + mock/种子兜底**：默认 `search_provider=none`
  → `online=false`、走种子候选；内置 **Tavily** 真实 provider（`SEARCH_PROVIDER=tavily` +
  `SEARCH_API_KEY` 即启用）。
- **需人工提供的搜索 API（任选其一启用真实联网）**：Tavily（推荐，已内置，单密钥，
  https://tavily.com）；或 SerpAPI / Bing Web Search / YouTube Data API v3 / arXiv API
  ——各实现一个 `web_search.SearchProvider` 子类即可接入，聚合层与接口签名不变。

## 文件清单
**新增（3）**
- `backend/app/services/web_search.py`：可插拔 `SearchProvider`（`_OfflineProvider` /
  `_TavilyProvider`）+ `get_provider()`；联网失败自动降级。
- `backend/app/services/resource_search.py`：聚合 Agent——provider 联网搜索 OR 种子兜底候选 →
  `LLMClient.aggregate_resources` 评分；薄弱点缺省由 Mastery 派生（因人而异）。
- `backend/tests/test_resource_search.py`：聚合契约 + 离线兜底 + 静态端点回归 共 5 用例。

**修改**
- `backend/app/core/config.py`：+`search_provider/search_api_key/search_base_url/...`（默认 none）。
- `backend/app/core/llm.py`：+`LLMClient.aggregate_resources`（聚合整理 + critic 评分，mock 确定性 /
  deepseek 真实，**URL 仅取自真实候选、防幻觉**）。
- `backend/app/schemas/resource.py`：+`ExternalAggregateRequest`。
- `backend/app/api/v1/resource.py`：+`POST /resource/external/aggregate`（套信封）。
- `frontend/src/services/resource.ts`：+`aggregateExternalResources`。
- `frontend/src/components/ResourceAggregator.tsx`：改用聚合端点 + online/offline 徽章 + 「重新联网搜索」。
- `frontend/src/pages/LearningResource.css`：徽章/刷新按钮样式。

## 接口文档增量（`docs/后端接口文档.md`，追加不重排）
- 8.6 增量（新增）`POST /resource/external/aggregate`：联网搜索聚合 + provider/online 语义 + 可插拔说明。
- 13 接口总览表：新增第 21b 行。既有 `GET /resource/external/{kpId}` 签名不变。

## 验证结果（live 实测 + 测试 + UI）
1. **无能力 mock 兜底可跑**：默认 `search_provider=none` → `POST /resource/external/aggregate {kpId:nn,
   weakPoints:[反向传播,梯度下降]}` → `provider:none online:false`，4 条候选经聚合 Agent 评分：
   视频 rel95/cred90、课程 85/100、文档 85/95、论文 80/100，**按相关度降序**，推荐理由结合薄弱点
   （deepseek 生成，因人而异）。
2. **UI 体现**：资源推荐区显示「📦 离线兜底（未配置搜索 API）」徽章 + 「🔄 重新联网搜索」按钮 +
   评分卡（相关性/可信度条 + 理由）；脚注引导配置搜索 API。浏览器 **0 console error**。
3. **配置即真实联网**：设 `SEARCH_PROVIDER=tavily` + `SEARCH_API_KEY` 后，候选改为 Tavily 实时
   联网命中（后端代理避配额/跨域），online=true，徽章变「🌐 联网搜索聚合」——签名与上层逻辑不变。
4. **回归 + 类型**：`pytest` **196 passed, 1 skipped, 0 失败**（含静态 `/resource/external/{kpId}`
   回归未变）；`tsc --noEmit` **0 报错**。

## 红线自检
- 既有接口签名未改：**新增** `POST /resource/external/aggregate`；既有 `GET /resource/external/{kpId}`
  逐字不变（回归用例保证）。
- 搜索源**可插拔**（`SearchProvider` 接口 + offline/Tavily 实现）+ mock/种子兜底。
- 统一信封；后端代理联网（前端不直连搜索 API，避配额/跨域）。
- Mock/真实双模式：聚合评分 mock 确定性 / deepseek 真实；无 Key、无搜索 API 均可跑。
- 防幻觉：聚合 Agent 输出 URL 一律取自真实候选，杜绝编造链接。
