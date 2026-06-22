# CC 会话三·完成总结（主资源生成选择性化 + 新用户接口空态兜底）

> 接 `CC-round3-followup.md` 两项任务。全程：已联调接口签名禁改、统一信封、Mock/真实双模式、复用优先、tsc 0 报错。

## 现状定位（任务1）

**主资源生成组件 = `frontend/src/pages/LearningResource.tsx` 的「🗂 资源中枢（browse）」模式。**
- 该页 5 个资源类型（讲义/视频/思维导图/图解/代码）与任务所列 5 类**逐一对齐**（`RESOURCE_CARDS`）。
- 改造前：进入资源中枢即**一次性整体呈现** 5 张卡片，点开走 layoutId 过场弹窗（讲义/视频/思维导图/图解/代码各自的富渲染器）；资源推荐是独立 aux-chip。**无勾选式选择、无逐项进度、无逐项呈现**——即本次要补的差距。

## 改动文件清单

### 任务1：主资源生成 → 选择性逐项生成 + 逐项进度 + 资源推荐进成果（保留卡片网格，上方加生成面板）
- `frontend/src/components/genStatus.tsx`（**新增**）：抽出共享状态原语 `ItemStatus / STATUS_META / StatusChip`，智能辅导面板与主资源生成两处共用，保证体验一致（不另造一套）。
- `frontend/src/components/TutorResourcePanel.tsx`：改为引用 `genStatus` 的共享 `StatusChip/ItemStatus`，删除本地重复定义（无行为变化）。
- `frontend/src/pages/LearningResource.tsx`：资源中枢顶部新增「✦ 资源生成」选择性生成面板——勾选 6 类（讲义/视频/思维导图/图解/代码 + 资源推荐）→ 逐项调用既有单类型接口（`getLecture`/`getVideo`/`getDiagram`；思维导图复用讲义结构化；代码为可运行示例占位；资源推荐复用 `fetchRecommendations`）→ 每项独立状态 + 顶部总进度条 → 生成完一项即解锁对应卡片；资源推荐并入成果区为第 6 张卡片（打开复用既有 `ResourceAggregator`）。未开始生成时卡片可直接浏览（不回归既有「查看资源」落点/费曼回看入口）。
- `frontend/src/pages/LearningResource.css`：新增生成面板/卡片锁定态/资源推荐卡样式（复用 `TutorResourcePanel.css` 的 `.trp__*`）。
- 复用 `TutorResourcePanel.css`（在本页 import）保证两处 UI/样式一致。

> 约束遵守：复用既有单类型生成接口（types 逐次单调用，契约不变）+ `fetchRecommendations`；未改任何接口签名；mock 兜底（mock 下短延时模拟逐项生成）。

### 任务2：student-portrait / knowledge-graph 新用户/空数据 → 干净 200 空态（防御兜底）
- `backend/app/services/student_portrait.py`：`get_portrait` 包裹兜底——任何异常 → 回滚并返回干净空画像（`dimensions:[] / version:v1 / updatedAt:null`），不冒泡 500。
- `backend/app/services/knowledge_graph.py`：`derived_nodes` 的掌握度/知识点映射查询包裹兜底——空数据/瞬时库异常 → 按「全部未开始」推导（12 静态节点恒返回），不冒泡 500。

> 说明：经实测，当前代码**happy path 本就返回 200 空态**（get-or-create 空画像 + 静态图谱节点）；本次为**防御性加固**，保证新用户/空数据/瞬时异常下恒得 200 空态（任务4 的契约保证）。

## 验证结果

### 任务1（真实 API 模式 `VITE_USE_REAL_API=true` + 后端在跑，Playwright 实测）
资源中枢 → 取消勾选「代码实操」→ 点「生成所选（5）」：
- 逐项生成、进度条推进至 **已完成 5/5**；
- 讲义/视频/思维导图/图解 卡片标记 **已完成** 且可点开；
- **代码实操 卡片 = 待生成 且 disabled（未勾选未生成）**；
- **资源推荐 卡片 = 已完成 · AI 已联网聚合 8 条**，点开正常呈现外部资源（复用 ResourceAggregator，站内播放保留）；
- 控制台 **0 errors**；与智能辅导面板使用同一套 `.trp__*` UI/样式，体验一致。
- `npx tsc --noEmit` → **0 报错**。

### 任务2（fresh user 实测 + 强制失败降级实测）
```
# 全新用户（fresh DB + 真实 dev 库副本）：
GET /api/v1/profile/student-portrait -> 200  code=0  {dimensions:[], version:v1, ...}
GET /api/v1/knowledge-graph          -> 200  code=0  {nodes:12, ...}
# 强制 mastery/get-or-create 抛错（验证降级）：
knowledge-graph(forced-fail)  -> 200  nodes=12（全未开始）
student-portrait(forced-fail) -> 200  {dimensions:[], version:v1, updatedAt:null}
```
- `pytest tests/test_dialogue_profile.py tests/test_b6.py` → **31 passed**。

## 红线自检
- ✅ 未改任何已定义接口路径/字段/枚举（仅在 `src/services/` 之上的页面复用既有数据获取层 + 后端 service 内部加兜底，响应结构不变）。
- ✅ 未改 Zustand store 结构、路由。
- ✅ 统一信封 `{code,message,data,traceId}` 不变；兜底走 `success(...)` 同信封。
- ✅ Mock/真实双模式均跑通；无 Key 也能跑（mock 短延时模拟逐项生成）。
- ✅ 未重构已验收阶段无关代码。

## 已知（非本次引入，超范围）
- `pytest` 全量：`test_resource_search.py::test_aggregate_offline_seed_fallback` 失败（`assert 'tavily'=='none'`）。根因：dev `.env` 的 `SEARCH_PROVIDER=tavily` 泄漏进测试（conftest 重置了 `LLM_PROVIDER=mock` 但未重置 `SEARCH_PROVIDER`）。**将本次两文件改动 stash 后该用例仍失败**——确属既有、环境驱动的测试隔离问题，与本次改动无关，未在范围内处理。
