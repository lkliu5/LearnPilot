# fix — 学习路径弹窗「开始学习」按钮无反应 · 修复总结

> 类型：缺陷修复（短会话）｜状态：✅ 完成（0 报错）｜日期：2026-06-11
> 现象：课程卡弹窗点「开始学习」三无（Console 无报错 / Network 无请求 / 无跳转），全部课程复现。

## 1. 根因（实证确认）

`LearningPath.tsx` 弹窗 `topic-modal__actions` 内的两个按钮**均未绑定任何 onClick**
（修复前 254-259 行只有 className，无事件处理）——「开始学习」与「查看资源」
自 mock 时代起都是纯占位按钮，从未接线。与「三无」实证完全吻合：
没有 handler，自然无报错、无请求、无跳转。「查看资源」行为同为无反应。

## 2. 修复方案

### 2.1 路由传参通道（新增 `src/services/resourceNav.ts`）

App 是 stage 状态机（无 URL 路由参数），页面经 `AnimatePresence` 按 key 重挂载。
新增轻量传参通道：**导航前由来源页写入、资源页挂载时读取**，等价于路由 query，
不触碰路由结构（CLAUDE.md 禁改路由；本通道即本次授权的「路由传参」层）：

- `setResourceNav(kpId, entryTab?)`：未知 kpId 回退默认 `CURRENT_KP_ID`(nn)；
- `getResourceKpId()`：**粘性**——资源页及子组件停留期间持续读取；侧边栏直达时
  保持上次值，初始为 nn，与修复前行为一致；
- `consumeResourceEntryTab()`：**一次性**（读后即清）——避免侧边栏再次进入时残留落点。

### 2.2 按钮接线（`LearningPath.tsx`）

`Lesson.sequence ↔ KnowledgePoint.lessonSeq`（`kpByLessonSeq`，6/6 全覆盖）：

| 按钮 | 行为 |
|---|---|
| 开始学习（primary） | `setResourceNav(kp.id)` → 资源页，落默认「定制讲义」Tab（学习主线） |
| 查看资源（secondary） | `setResourceNav(kp.id, 'external')` → 资源页，落「资源推荐」Tab（外部资源聚合） |

**取舍说明（要求 3）**：选「各司其职」而非统一——资源页本身就是该知识点全部
多模态资源的聚合页，两按钮目的地相同；差异落在**落点 Tab**：「开始学习」按主线
从讲义学起，「查看资源」直达外部精选资源，语义与按钮文案一一对应，且仅靠既有
`tab` state 的初值实现，UI 结构/样式零改动。

### 2.3 资源页按 kpId 请求（`LearningResource.tsx` + 两个子组件）

- `kpId = USE_REAL_API ? getResourceKpId() : CURRENT_KP_ID`：联调全 Tab 按传参
  kpId 请求；**mock 模式恒为 nn**——本地演示内容只有 nn 一套，避免「标题 CNN、
  内容 nn」的错配（mock 下点击至少正确跳转资源页，行为不再是无反应）。
- 讲义/测验/提交/检验闭环（`getLecture/getQuiz/submitQuiz/goCheck/markPassed`）、
  外部资源（`ResourceAggregator`）、错题强化（`WeakPointReinforce`）全部改用动态 kpId。
- 测验题联调初值由 nn 演示题改为 `[]`：避免拉取期间闪现错误知识点的题目。
- **思维导图**：后端 8.4 导图接口（接口 19）未实现——采用数据层方案：联调时由
  当前讲义 markdown 实时结构化为标题大纲（`lectureOutline`，跳过代码块内 `#` 注释行），
  讲义本身按 kpId 请求故大纲随 kpId 变化，与组件文案「AI 已将讲义结构化为知识脉络图」
  一致；mock 保持本地大纲常量。
- **友好占位（要求 2）**：讲义未就绪 /导图待结构化 / 测验题为空时，复用既有
  `resource-loading` 样式给出带知识点名的提示文案，零新增 CSS。

## 3. 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/services/resourceNav.ts` | **新增**：路由传参通道（kpId 粘性 + entryTab 一次性） |
| `src/pages/LearningPath.tsx` | 弹窗两按钮接线 `openResource(topic, entryTab?)`（仅加 onClick，按钮结构/样式未动） |
| `src/pages/LearningResource.tsx` | kpId 动态化（8 处引用）、落点 Tab 初值、测验联调初值 `[]`、导图大纲结构化、三处友好占位 |
| `src/components/ResourceAggregator.tsx` | 外部资源请求 kpId 改读传参通道（仅联调分支） |
| `src/components/WeakPointReinforce.tsx` | 错题上报 kpId 改读传参通道（仅联调分支） |
| `backend/scripts/verify_fix_start_learning.py` | **新增**：6 KP × 资源页三件套等价请求回归脚本 |

> 严格未触：路由结构（App stage 状态机）/ Zustand store / CSS / 动效 / 弹窗及
> 资源页 UI 结构（占位为既有样式类的条件渲染，按要求 2 属交付内容）。

## 4. 验证（0 报错）

### ① 类型检查
```
npx tsc --noEmit -p tsconfig.json   →  EXIT 0
```

### ② 6 个课程卡「开始学习」等价请求逐一实测（8000 实例，provider 按本机 .env）
```
[seq 1 -> ml         ] quiz=3题 lecture=2597字(sources=2) external=4条 outline=12行 首行=# 机器学习基础讲义
[seq 2 -> nn         ] quiz=3题 lecture=2049字(sources=2) external=4条 outline=9行  首行=# 神经网络基础讲义
[seq 3 -> dl         ] quiz=3题 lecture=2187字(sources=1) external=4条 outline=17行 首行=# 深度学习原理讲义
[seq 4 -> cnn        ] quiz=3题 lecture=2243字(sources=2) external=3条 outline=16行 首行=# CNN架构讲义
[seq 5 -> transformer] quiz=3题 lecture=892字(sources=2)  external=4条 outline=6行  首行=# Transformer 架构讲义
[seq 6 -> finetune   ] quiz=3题 lecture=1694字(sources=2) external=4条 outline=11行 首行=# 大模型微调技术
ALL 6 KP RESOURCE-PAGE-EQUIVALENT CHECKS PASSED (code 0)
```
- 三件套（GET /quiz/{kp}、POST /resource/lecture、GET /resource/external/{kp}）
  ＝点击「开始学习」后资源页实际发出的请求，6/6 全 code 0；
- 大纲提取按前端同款规则在脚本内复算：全部非空、未混入代码块内注释行
  （导图 Tab 对全 6 KP 有内容，占位分支为讲义未就绪时的过渡态）。

### ③ Vite transform
```
GET /src/services/resourceNav.ts / LearningPath.tsx / LearningResource.tsx
    / ResourceAggregator.tsx / WeakPointReinforce.tsx   → 全部 200，无 transform 报错
```

### ④ 诚实声明
- 同前：无浏览器自动化工具，「逐一点击 6 卡」未做 DOM 级自动断言；已验证
  点击路径的全部确定性环节——映射（lessonSeq↔kpId 6/6）、传参通道（tsc 两分支
  编译覆盖）、页面发出的等价请求（6 KP × 3 接口 code 0）。建议手动走查一遍：
  卡片视图/时间线点课程 → 弹窗「开始学习」→ 应进入对应知识点资源页（标题徽章
  显示该知识点名），「查看资源」→ 同页落「资源推荐」Tab。
- mock 模式（`VITE_USE_REAL_API=false`）下按钮同样接线生效，但资源页内容恒为
  nn 演示集（设计取舍见 2.3），徽章亦显示 nn——评审离线兜底口径。
