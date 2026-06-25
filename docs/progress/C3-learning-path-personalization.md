# C3 学习路径真个性化：能力定顺序 · 偏好定形式 · 画像变路径变

> 让学习路径真正因画像而变（不再"写死"）。
> 0 报错完成：后端 `pytest 207 passed, 1 skipped`；前端 `tsc --noEmit` 干净（exit 0）。

## 一、定位结论（写死在哪层）

| 层 | 结论 | 证据 |
|---|---|---|
| **planner 输入** | ✅ 真实，未写死 | `plan_path` 读真实 `StudentPortrait` + `Mastery` + 岗位需求 |
| **planner 逻辑** | ⚠️ 部分写死 | ① 排序只用 Mastery **status**（passed/learning），**不消费 C2 微测写入的 per-KP 能力分** → 无法"某点测得好后置、测得差优先"；② `_build_resources` 每节点返回**固定 6 种资源、同一顺序**，**不消费偏好画像** → "每步怎么学"无个性化 |
| **前端展示** | ❌ **完全写死** | `LearningPath.tsx` `import { lessons } from '../data/learningPath'`（静态）+ 硬编码 milestones，**根本不调后端 `/learning-path`**——后端算对了也不显示（个性化"消失"最致命的一层） |
| **缓存** | ⚠️ 无失效 | `Journey.path_plan` 缓存无指纹，画像变不重算 |

## 二、改动文件清单

**后端（改 5）**
- `app/agents/planner_agent.py`：① 排序消费 `Mastery.score`（per-KP 能力分）——能力分 ≥70「已达标后置」、薄弱点（低分/未测）按先修前置；② `_build_resources` 按认知风格+学习节奏排资源形式，首项 `recommended`+`recommendReason`；③ 新增 `portrait_fingerprint()`；④ `plan_path(narrate=False)` 确定性零网络模式。
- `app/core/llm.py`：`_mock_plan_path` 加「微测达标→后置」理由分支 + 能力分扣题 + 摘要含偏好"怎么学"；`plan_path(deterministic=…)`。
- `app/api/v1/learning_path.py`：GET 按**画像指纹**判定缓存命中/实时重算（画像变→路径变，不写死）；`summary.narrative` 回传规划叙述；generate 写指纹+叙述。
- `app/models/entities.py`：`Journey` 加 `path_fingerprint`/`path_narrative`（可空）；`app/core/init_db.py` 幂等迁移。

**前端（改 3）**
- `services/learning.ts`：路径类型加 `kpId/reason/resources(含recommended)`/`summary.narrative`；`getLearningPath()` 真调后端，**Mock 兜底本地合成等价个性化路径**（镜像 planner：能力分排序 + 偏好资源 + 理由）。
- `pages/LearningPath.tsx`：**改为真取后端路径**（不再用静态 `data/learningPath`）；画像/掌握度变 → 重新拉取（重算）；渲染规划理由横幅 + 每步 reason + 每步「为你推荐」资源形式。
- `pages/LearningPath.css`：规划理由/每步理由/推荐资源样式。

**测试**：`test_learning_path_planner.py` 新增 per-KP 顺序 + 偏好资源 + GET 画像变重算 2 例；`test_contract_snapshot.py` 放开 6.1 additive（lesson `kpId/reason/resources`、summary `narrative`）。

## 三、接口文档增量（`docs/后端接口文档.md` 6.x）

- **6.1**：`summary.narrative`（规划叙述）additive；GET 画像指纹不符→实时重算（不缓存写死）。
- **6.3**：per-KP 能力分定顺序（≥70 后置、薄弱前置）；`resources[].recommended`/`recommendReason`（偏好定资源形式）。

## 四、验证结果（两个对比鲜明的学生 · 真实 API）

**验证1+4：两用户路径对比（节点/顺序/推荐资源形式都不同）**

| | 用户A：AI基础好(基础强/进阶弱)+图像型 | 用户B：零基础(全弱)+案例型/细钻 |
|---|---|---|
| 顺序 | **CNN→Transformer→微调→[ml/nn/dl 复习]**（直奔进阶） | **ml→nn→dl→CNN→Transformer→微调**（从头学，先修序） |
| 首步 | CNN架构 [高级] | 机器学习基础 [入门] |
| 默认推荐资源 | **知识图解 diagram**（图像型） | **精选外部资源 external**（案例型） |
| 首步理由 | 「CNN架构」是你的薄弱点（微测能力分 40），第 1 步集中攻克 | 「机器学习基础」是基础且未掌握，第 1 步打牢根基 |

**验证2：画像变 → 路径变**
用户B 重做诊断（零基础→基础好/进阶弱）→ 顺序由 `ml→nn→dl→CNN→Transformer→微调`（从头学）
**变为** `CNN→Transformer→微调→[基础复习]`（直奔进阶），难度整体上调（入门→高级/精通）——**不再写死**。

**验证3：规划理由可感知**
GET `summary.narrative` = "本路径依据你的画像（基础扎实）与各知识点实测能力规划：将 3 个薄弱点前置、
3 个已达标点后置复习，共 6 步；并按你的学习偏好（图像型·快速概览型）为每步默认推荐最适合的资源形式…"；
每步 `reason` 扣住实测能力分；前端横幅 + 每步理由 + 每步「为你推荐」资源形式呈现。

**验证4：零回归**：后端 `pytest 207 passed, 1 skipped`（+2 新例）；前端 `tsc` exit 0。

## 五、红线自检

- ✅ **不改既有接口签名**：`summary.narrative`、`resources[].recommended/recommendReason`、`Journey` 2 列均为**追加**；旧前端透明（结构化类型忽略多余字段）。
- ✅ **复用现有 planner / 资源类型 / 画像**：未重建；能力分来自 C2 Mastery（口径统一）、偏好来自 C2 画像。
- ✅ **Mock 兜底**：无后端时 `getLearningPath()` 本地合成等价个性化路径（能力分排序 + 偏好资源 + 理由），全链路跑通。
- ✅ **不破坏 C2 画像与下游一致性**：能力分/偏好直接复用 C2 结构；GET 指纹覆盖画像/掌握度/岗位变化。
- ⚠️ **GET 实时重算改变了缓存语义**：原 GET 只读缓存/种子；现已诊断用户首访/画像变时即时重算（确定性、零网络、不阻塞），并回填缓存；正式"生成"里程碑仍由 POST `generate` 置位（`has_generated_path` 不被 GET 改动）。
