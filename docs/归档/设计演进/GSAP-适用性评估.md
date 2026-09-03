# GSAP 适用性评估 · 智学中枢前端

> 评估日期：2026-06-01
> 对象：[GSAP (GreenSock Animation Platform)](https://github.com/greensock/GSAP) v3.15
> 结论：**建议引入，但作为 Framer Motion 的「补充」而非替代**——只用它做 Framer/CSS 做不好的 3 类动画。

---

## 一、GSAP 是什么

框架无关的高性能 JS 动画库，可驱动 CSS / SVG / Canvas / WebGL / 任意 JS 对象。特点：
- **现已 100% 免费**（Webflow 赞助），含全部原插件：ScrollTrigger、SplitText、MorphSVG、Flip、Draggable、**MotionPathPlugin**、Observer 等。
- 零依赖，约 50KB gzip（core）；号称比 jQuery 快 20×；驱动 1200 万+ 网站。
- React 集成：`@gsap/react` 提供 `useGSAP()` Hook（自动清理，替代 useEffect/useLayoutEffect）。
- 强项：**时间轴精确编排、数值缓动、沿路径运动、文字拆分动画、滚动驱动**。

## 二、本地部署状态 ✅ 已完成并验证

```bash
npm install gsap @gsap/react      # gsap 3.15.0 + @gsap/react 2.1.2
```
- 新增 `src/hooks/useCountUp.ts`（GSAP 数字滚动 Hook）。
- 概念验证：学情概览「综合能力分」加载时 **从 0 缓动到 72.5**。
- **实测验证**：高频采样捕获到 43 个递增中间帧（`0.0→8.9→26.7→…→72.5`），呈 `power2.out` 减速曲线；**0 控制台错误**，构建正常。
- GSAP 零依赖，不新增第三方漏洞面（项目现有 5 个 moderate 漏洞来自 Vite/esbuild 工具链，与 GSAP 无关）。

## 三、现状动画栈

| 工具 | 当前用途 |
|------|---------|
| Framer Motion | 页面切换、入场 stagger、hover、layout 指示器 |
| ECharts | 雷达图动画 |
| CSS keyframes | 光晕浮动、脉冲、ping 波纹、时间线流光、连线 dash-flow |

## 四、GSAP 在本项目的适配点（按价值排序）

| # | 应用点 | 价值 | Framer/CSS 能否做 | 建议 |
|---|--------|:---:|------|------|
| 1 | **Agent 大屏：消息粒子沿连线流动**（MotionPathPlugin） | ★★★ | ✗ CSS 仅能 dash 位移近似，无法真实沿路径走点 | **强烈推荐**——正是赛题「多智能体协同」的视觉核心，目前是 CSS 占位 |
| 2 | **数值滚动**（gauge 72.5 / 统计 65%·3·12 / 评分 / 结果页） | ★★ | △ Framer 可用 motionValue 但繁琐 | **推荐**——已 POC 验证，仪表盘质感提升明显 |
| 3 | **标题/欢迎语文字逐字入场**（SplitText） | ★★ | ✗ Framer 难、需手动拆字 | **推荐**——「智学中枢」「你好，学习者」逐字/逐词揭示，独特高级感 |
| 4 | 滚动驱动揭示（ScrollTrigger） | ★ | ✓ Framer whileInView 已能做 | 可选——边际价值低，除非要滚动「擦除」类高级效果 |
| 5 | 布局/视图切换（Flip） | ○ | ✓ Framer AnimatePresence/layout 已覆盖 | 不必——避免重复造轮子 |
| 6 | AgentWorkflow 时序编排（Timeline） | ○ | △ 现 setTimeout 链可工作 | 可选重构——更易暂停/回放，但属逻辑层 |

## 五、推荐策略

**共存，不替换**：
- **保留 Framer Motion** 做它擅长的：页面/入场过渡、layout、手势。
- **引入 GSAP** 仅做 3 件 Framer/CSS 做不好的事：① Agent 连线粒子流（MotionPath）② 数值滚动 ③ SplitText 文字揭示。
- 理由：双动画库会增体积与心智成本，**唯有用到 GSAP 的独有插件（MotionPath / SplitText）才划算**；若只做数值滚动，留在 Framer 亦可。故最强理由是 ①③。

**动效纪律**（沿用 disign.md）：轻、柔、慢、克制，时长 0.3–1.6s，缓动 `power2.out`/`power3.out`，禁止夸张弹跳。

## 六、落地路线

| 阶段 | 内容 | 文件 | 状态 |
|---|---|---|:---:|
| G1 | Agent 大屏连线改 MotionPath 真粒子流（替换 CSS dash 占位） | AgentWorkflow.tsx/.css | ✅ 完成 |
| G2 | 数值滚动推广到所有仪表数字（复用 useCountUp） | useCountUp.ts · CountUp.tsx · Dashboard / ProfileBuilder / AgentWorkflow | ✅ 完成 |
| G3 | SplitText：欢迎语 / 各页大标题逐字入场 | SplitReveal.tsx + 4 页标题 | ✅ 完成 |

### G1 实现要点（已完成 2026-06-01）
- `useLayoutEffect` + `ResizeObserver` **测量真实节点中心坐标** → 生成 4 条二次贝塞尔曲线路径（替换原 `<line>` 百分比近似坐标，连线现精确连接节点中心）。
- 运行态用 `useGSAP` + `MotionPathPlugin`：每条边 2 个粒子（错峰 0.85s），沿 `#edge-path-*` 路径 `淡入→沿路径 1.7s→淡出` 循环；停止时 timeline 自动 kill、粒子卸载。
- **实测验证**：粒子坐标随路径变化（如诊断边 `y:317→264→261` 向上行进）、opacity 沿程 0.25↔0.46 渐变；运行态 8 粒子（2×4 边）；连线由直线近似改为精确曲线；0 控制台错误。
- 附带收益：连线不再是「大致指向」，而是数学精确连接节点中心，并随容器 resize 自适应。

### G2 实现要点（已完成 2026-06-01）
- 强化 `useCountUp`：支持 `prefix/suffix`，并**从「上一次显示值」缓动到新目标**（而非每次从 0）——使实时统计平滑增量。
- 新增 `<CountUp>` 组件：渲染**空 span 由 GSAP 接管文本**，规避父组件重渲染（学情概览时钟每秒刷新）覆盖动画值；可在 `.map()` 中安全使用（各实例独立调用 Hook）。
- 覆盖数值：学情概览 gauge `72.5` + 4 张统计卡（`65%·3·3·12`）、画像结果页（`72.5` + 已评估数）、Agent 工作流统计（已完成 Agent / 消息数 / 进度%）。
- **实测验证**：gauge `0.0→72.5`（54 帧）；统计卡至 `65%`（suffix 保留）；工作流「已完成Agent」运行中 `0→1→2→3` 单调增量（无回弹归零）、终值 `3/6/100%`；时钟每秒重渲染不覆盖；0 控制台错误。

### G3 实现要点（已完成 2026-06-01）
- 新增 `<SplitReveal>` 组件：用 GSAP **SplitText** 把标题拆成字符，`gsap.from` 逐字 `y+opacity` 错峰揭示（stagger 0.035s，power3.out）；卸载 `split.revert()` 还原 DOM。
- **`memo` 包裹**：避免学情概览每秒时钟重渲染触发 React 协调而擦掉 SplitText 注入的字符节点。
- 覆盖标题：欢迎语「你好，学习者_001 👋」、画像诊断「学习者画像构建」、学习路径「个性化学习路径」、Agent「智能体协同调度大屏」（均为实色标题，避开渐变文字的 clip 冲突）。
- **实测验证**：欢迎语拆为 11 个字符容器（`<div aria-hidden translate...>`）；切到学习路径标题正常拆分，切回学情概览文本完整且重新揭示（revert+重挂载无破坏）；布局无错位；0 控制台错误、无 SplitText license 警告（免费版正常）。

---

## 七·补、talizen 式动效落地（参考 talizen.com）

> 借用 talizen 的动效词汇（深色电影感 + 选择性渐变标题 + 滚动巨字聚光 + 滚动渐显），用在合适位置，不改浅色仪表盘内部气质。GSAP ScrollTrigger 随 gsap 免费，零新增重型依赖。

| 阶段 | 内容 | 文件 | 状态 |
|---|---|---|:---:|
| T1 | 滚动叙事落地页（Hero 选择性渐变 + 滚动巨字聚光序列）| Landing.tsx/.css · App.tsx | ✅ |
| T2 | 登录页升级为 talizen 风（近黑底 + 选择性渐变大标题 + 巨字虚影）| Login.tsx/.css | ✅ |
| T3 | 仪表盘滚动渐显（浅色不变，区块进视口淡入上浮）| useScrollReveal.ts · Dashboard.tsx | ✅ |

### T3 实现要点（已完成 2026-06-01）
- 新增 `useScrollReveal`：scope 内 `[data-reveal]` 元素 `gsap.set` 隐藏 → 进入视口由 GSAP 淡入上浮；加到学情概览两条下半屏双栏行（推荐路径 / Agent 状态）。
- **踩坑与修复**：初版用 `ScrollTrigger { scroller: '.app__main' }`，因该容器实际高度=内容高度（未约束）→ 不滚动，scroller 选择器解析异常触发 **`Cannot read properties of undefined (reading '_gsap')`** 使 Dashboard 崩溃。
- **改用 IntersectionObserver 触发 + GSAP 执行动画**：不依赖具体滚动容器（规避 `.app__main`/window 滚动模型歧义），元素在视口内即渐入、否则滚动到时渐入。彻底消除崩溃。
- **实测验证**：两行初始 `opacity:0`（下半屏隐藏）→ `scrollIntoView` 后 GSAP 渐入至 `opacity:1`；浅色玻璃风格不变；0 控制台错误。

---

## 七·补二、three.js 粒子漩涡（落地页 Hero 背景）

> 将外部 `particle-vortex-effect.html`（three.js WebGL 漩涡）融合进落地页 Hero。

- **新增依赖**：`three` 0.184（~150KB gzip）+ `@types/three`。
- **新增组件** `components/ParticleVortex.tsx`：React 封装 three.js 场景。
  - 仅保留 **程序化漩涡**（effectMode 3），**丢弃原 1.2MB base64 图片**与其它 5 种特效/图片 morph/模型加载逻辑 → 轻量化。
  - **品牌重配色**：原绿/白 → 蓝(`#60a5fa`)/紫(`#a78bfa`)/浅蓝(`#dbeafe`)。
  - 粒子数 11 万 → **5.5 万**（兼顾观感与性能）；透明画布叠加在落地页深色背景之上；自动旋转、`pointer-events:none`（不拦截点击/滚动）。
  - **彻底清理**：卸载时 cancelAnimationFrame + geometry/material/renderer.dispose + 移除 canvas，杜绝 WebGL 上下文泄漏。
- **落地页接入**：Hero 加 `<ParticleVortex>` 背景层 + 径向暗角 scrim（保证标题在亮粒子上可读），文字层 `z-index` 抬升。
- **实测验证**：Hero 蓝紫漩涡渲染正常、标题清晰、`进入系统` 点击穿透生效（canvas 不挡）、落地页卸载后 `canvas` 数归 0（无泄漏）、0 控制台错误。

---

## 八、GSAP 集成总结（G1–G3 + T1–T3 全部完成）

| 能力 | 落地 | GSAP 独有性 |
|------|------|------|
| Agent 连线真粒子流 | MotionPathPlugin 沿测量曲线走点 | ✅ Framer/CSS 无法实现 |
| 数值滚动 | useCountUp + CountUp 组件，全站仪表数字 | △ Framer 可做但繁琐 |
| 标题逐字揭示 | SplitText + SplitReveal 组件 | ✅ Framer 难实现 |
| 滚动叙事落地页 | ScrollTrigger 巨字聚光序列 | ✅ talizen 签名效果 |
| 滚动渐显 | IntersectionObserver + GSAP | ○ 健壮性优先 |

**最终形态**：GSAP 与 Framer Motion **共存**——Framer 管页面/入场/手势，GSAP 管「沿路径运动 + 数值缓动 + 文字拆分 + 滚动叙事」。新增可复用资产：`useCountUp.ts`、`CountUp.tsx`、`SplitReveal.tsx`、`useScrollReveal.ts`、`Landing.tsx`。全程零控制台错误，契合赛题「多智能体可视化」重点。

## 七、结论

GSAP **适合**本项目，且**契合赛题重点**（多智能体可视化）。建议以「补充 + 独有插件优先」的方式引入，从 **Agent 大屏粒子流（G1）** 切入收益最大。是否全面推广、保留还是回退当前 POC，待确认。
