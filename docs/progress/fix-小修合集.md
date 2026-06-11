# fix — 小修合集（三项独立小改）· 完成总结

> 类型：缺陷修复/小改（短会话）｜状态：✅ 完成（0 报错）｜日期：2026-06-11
> 三项排查结论：**第 1、3 项此前已修复**（提交 `3406853`，记录见
> `docs/progress/fix-手动填写岗位列表.md`），本次仅复核确认无回归；
> **第 2 项为本次新实现**（知识图谱节点点击分流）。

## 1. 逐项处置

### ① 画像诊断「手动填写」目标岗位选择器为空 → 已有修复记录，复核通过

- 记录：`docs/progress/fix-手动填写岗位列表.md`（提交 `3406853`，2026-06-11 20:03）。
- 该修复已满足本次要求：手动填写与材料上传**共用** Step1 的 `JobMarketPanel`，
  数据源统一为 `GET /job-market/hot`（`getHotJobs`）；降级链「code 2002（okCodes
  白名单）/ 空列表 / 请求失败 → **预置 4 岗兜底 + offline 标记**」——2002 离线时
  仍可选预置岗，选择器永不为空。
- 本次复核：hot 实测 code 0、4 岗（见第 3 节实测 ②），无回归，**未改任何代码**。

### ② 知识图谱节点点击分流 → 本次实现

- **核心 6 节点**（`ml/nn/dl/cnn/transformer/finetune`，即 `KNOWLEDGE_POINTS`
  注册表全集，经 `kpByGraphNode` 命中判定）点击 → `setResourceNav(kp.id)` +
  `onNavigate('learning-resource')` 跳转对应知识点资源页——与学习路径页
  「开始学习」**同款导航通道**（resourceNav 路由传参，资源页挂载时读取 kpId）。
- **非核心 6 节点**（rnn/attn/bertgpt/prompt/rag/agent）点击 → 轻提示
  「『{节点名}』暂未开通课程，作为领域拓扑参考」，3.2s 自动消失。
- 提示**复用 AdminKB/AdminPrompts 的 `.akb__toast glass-card` 既有 toast 形态**
  （同类名、同 motion 参数），零新增样式；ECharts 点击处理器在既有 option effect
  内注册（先 `off('click')` 再 `on`，防止 effect 重跑堆叠）；mock / 联调两种
  数据源下节点 id 集合一致（12 节点），分流行为相同。

### ③ 岗位市场页右上角「联网快照·缓存」页级标签跟随 offline → 已有修复记录，复核通过

- 同提交 `3406853` 的「顺手项」（修复文档第 2 节末段）：`JobMarketPanel` 经可选
  `onOffline` 回调上抛离线状态（热门列表降级 或 当前快照降级任一为真），
  页级徽章文案动态化——离线 → **`离线快照 · 预置库`**，正常 → `联网快照 · 缓存`
  （`ProfileBuilder.tsx:376`，同一 span / 同一 `pb-badge` 样式类，仅文案变化）。
- 本次复核代码接线完整（state→callback→徽章三段均在），**未改任何代码**。

## 2. 改动文件清单（仅第 ② 项，2 个）

| 文件 | 改动 | 边界 |
|---|---|---|
| `src/pages/KnowledgeGraph.tsx` | 新增可选 `onNavigate` prop（与兄弟页面同形）；option effect 内注册节点 click 分流；toast state + AnimatePresence 块（复用 `.akb__toast` 样式，引入 `admin.css` 获取该类，类名均 `akb__` 前缀无污染） | ECharts 配置/力导参数/tooltip/legend/着色逻辑零改动；本地种子与联调数据源择一逻辑未动 |
| `src/App.tsx` | `<KnowledgeGraph />` → `<KnowledgeGraph onNavigate={navigate} />` | 仅补传兄弟页面（Dashboard/LearningPath 等）均已持有的同一 navigate；路由结构/stage 状态机零改动 |

> UI 结构/样式零新增：toast 为既有样式类复用；无新 CSS、无新组件文件。

## 3. 验证（0 报错）

### ① 类型检查
```
npx tsc --noEmit -p tsconfig.json   →  EXIT 0
```

### ② 逐项实测（经 :3000 dev server，后端 :8000）
```
[vite] /src/pages/KnowledgeGraph.tsx -> 200
[vite] /src/App.tsx -> 200
[graph] code 0 nodes= 12
[item2] 跳转分支(核心6命中): ['cnn', 'dl', 'finetune', 'ml', 'nn', 'transformer']
[item2] 轻提示分支(非核心):   ['agent', 'attn', 'bertgpt', 'prompt', 'rag', 'rnn']
[hot]   code 0 n= 4 ['llm-app', 'algo-engineer', 'ml-engineer', 'data-analyst']
```
- ②：后端真实图谱 12 节点恰好 6+6 划分，两条点击分支均有真实数据可达；
  跳转用的 `setResourceNav` → 资源页读取链路为既有路径（学习路径页同款，已验收）。
- ①③ 复核：hot 4 岗 → 选择器有岗可选；标签条件渲染接线在源码层确认。

### ③ 诚实声明
- 无浏览器自动化工具，「点击节点跳转 / toast 弹出」未做 DOM 级断言；分流判定
  （注册表命中）、导航通道（resourceNav）、提示组件形态（AdminKB 同款）均为
  已验收机制的组合复用。建议手动走查：知识图谱页点「神经网络基础」应跳资源页
  且内容为 nn；点「RNN架构」应弹底部轻提示后自动消失。
- 第 ①③ 项未重复造轮子：以复核代替重做，结论与既有修复文档一致。
