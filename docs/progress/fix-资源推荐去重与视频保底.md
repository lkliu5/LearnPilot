# fix - 资源推荐（联网聚合）：重复生成去重 + 结果至少含 1 条视频

> 2026-07-13 · commit `2f6fa37`（附带 `6f90a1f` gitignore 小尾巴）
> 范围：问题修复（非 B 阶段）；接口路径/字段/枚举零改动。

## 问题与根因

### 问题 1：同一份推荐生成两遍
现象：进入资源推荐弹层，已展示 4 个资源卡，右上角仍显示「联网搜索中…」并再触发一轮检索。

根因（Playwright 抓包定位，两个 POST 请求体不同）：
1. hub「资源推荐 · 立即查看」先跑 `generateOne('external')` → `fetchRecommendations`，为拿条数发第一轮聚合（`weakPoints=[知识点名]`）；
2. 弹层 `ResourceAggregator` 挂载后 `useEffect` 无条件再发第二轮（`weakPoints=[]`）；
3. 弹层初始 state 为 4 条静态种子卡，联网期间被当结果展示 →「已有结果却还在搜索」的错觉；
4. 结果随组件卸载丢弃、无缓存，再次打开重来（StrictMode 双挂载进一步放大）。

### 问题 2：推荐结果可能一条视频都没有
排序只按「相关性 + 可信度」截 Top-8，无形态约束。实测还发现三层缺口：
- Tavily 通用搜索经常一条视频 URL 都不返回（nn/cnn 实测 0 视频）；
- cnn 种子库本无视频；
- AGT-1 等体系拓展点无任何专属种子 → 离线兜底时推荐直接为空。

## 修复方案

### 问题 1（前端，缓存下沉到 services 数据获取层）
- `services/resource.ts` 新增 `loadAggregateCached` / `getAggregateCached`：按 kpId 会话级缓存 + 在途 Promise 去重；`force=true` 才重拉。
- `ResourceAggregator.tsx`：挂载改走共享缓存（命中零请求、瞬时展示）；首拉期间展示真实「联网搜索中」占位（`.agg__searching`，不再把种子卡伪装成结果）；「重新联网搜索」按钮传 force；失败仍回落种子兜底。
- `LearningResource.tsx`（数据获取层单点替换，CLAUDE.md 允许范围）：`generateOne('external')` 改用 `loadAggregateCached`，与弹层共享同一次请求。

### 问题 2（后端，三层保底）
- `llm.py` `_ensure_video(ranked, limit=8)`：Top-N 无视频 → 用候选池最高分视频替换 Top-N 中评分最低的非视频项（总数不变、重排后仍按相关度降序）；候选池确实无视频 → 不硬塞，`logger.info` 可解释降级。mock / deepseek 两路统一接入。
- deepseek 排序提示词追加：「形态尽量多样（视频/课程/论文/文档兼顾），候选存在视频时清单至少含 1 条视频」；LLM 把视频候选全部丢弃时，用确定性评分回补最优视频候选再进保底。
- `resource_search.py`：联网命中无视频 → 从精选种子库补充 ≤2 条视频候选（真实 URL、可站内嵌播，最终取舍仍由聚合评分决定）；无专属种子的体系拓展点 → 回落全库精选池（limit 12），保证任意在库 kp 推荐非空且含视频。
- `init_db.py`：cnn 补 1 条视频种子（3Blue1Brown「什么是卷积？」，含 embed）。

## 文件清单

| 文件 | 改动 |
|---|---|
| `frontend/src/services/resource.ts` | 新增 `AggregateSnapshot` / `getAggregateCached` / `loadAggregateCached`（缓存 + 在途去重） |
| `frontend/src/components/ResourceAggregator.tsx` | 挂载走共享缓存；搜索占位；force 刷新 |
| `frontend/src/pages/LearningResource.tsx` | `generateOne('external')` 改用共享缓存加载器（仅数据源调用替换） |
| `frontend/src/pages/LearningResource.css` | 新增 `.agg__searching` / `.agg__searching-orb` 占位样式 |
| `backend/app/core/llm.py` | `_ensure_video` 保底 + 两路接入 + 提示词多样性约束 + 视频候选回补 |
| `backend/app/services/resource_search.py` | 联网无视频补种子视频候选；无专属种子回落全库精选 |
| `backend/app/core/init_db.py` | cnn 视频种子 `cnn-r4` |
| `backend/tests/test_resource_search.py` | 新增 5 用例（见下） |

## 启动命令

```bash
cd backend && uvicorn app.main:app --port 8000
cd frontend && npm run dev
```

## 验证命令与实测结果

```bash
cd backend && python -m pytest tests/test_resource_search.py -q   # 10 passed
cd backend && python -m pytest -q                                 # 290 passed, 1 skipped
cd frontend && npx tsc --noEmit                                   # 0 错误
```

新增 pytest 用例：
- `test_video_guarantee_swap`：Top-8 无视频 → 最高分视频换入、总数不变、仍降序；
- `test_video_guarantee_already_present`：已含视频不做替换；
- `test_video_guarantee_degrade_without_video`：候选池无视频 → 可解释降级；
- `test_aggregate_offline_contains_video`：nn/cnn 种子兜底聚合均含视频；
- `test_aggregate_catalog_kp_generic_seed_fallback`：AGT-1 全库兜底非空且含视频。

Playwright 实测（真实 Tavily + DeepSeek 链路，`.playwright-mcp/agg-*.png`）：
- **只生成一次**：nn / cnn / AGT-1 三个知识点，「立即查看 → 弹层出结果」全程各恰好 1 个 `POST /resource/external/aggregate`；
- **复用**：关闭重开弹层 0 新请求、结果瞬时展示、无「联网搜索中」；
- **显式刷新**：点「重新联网搜索」精确多发 1 次，刷新期间旧卡保留、按钮显「联网搜索中…」；
- **视频保底**（API 层每 kp 跑 2 轮）：nn 1 视频（保底替换生效）、cnn 2 视频、AGT-1 2 视频，全部 PASS；
- 浏览器 0 console error（仅 1 条与本改动无关的 THREE.js 弃用告警）。

## 备注

- 保底优先级：真实联网视频命中 > LLM 排序自带视频 > 种子库视频候选补位 > `_ensure_video` 替换 > 可解释降级（日志）。
- 验证过程中出现过一次 401 踢回首页：浏览器会话 JWT 过期（登录于当日 00:59），属环境事件，与本修复无关，重登复测通过。
