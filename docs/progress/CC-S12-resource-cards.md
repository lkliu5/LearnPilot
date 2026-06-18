# CC 指令 · S12 — 资源中枢卡片化（插画缩略图 + 点击过场动画）

> 对应第二轮测试反馈"按钮多、没重点"的最终方案。仅改前端、不动后端与接口；用户已确认卡片插画风格。
> 全局纪律照旧：已联调接口签名禁改、复用现有设计令牌与组件、Mock/真实双模式、完成即停、tsc 干净 0 报错。

═══════════════════════════════════════════════════════════════

# 角色
资深前端工程师（React 18 + TS + Vite + Framer Motion）。项目已联调。本会话重构「学习资源页 · 资源中枢模式」为卡片式，不改后端、不改任何接口签名。

# 范围与前提
- 只改 **资源中枢（browse）模式**；**有序学习模式（费曼+康奈尔流）保持不变**。
- **不新增任何竖直导航**——卡片是"内容入口"，左侧已有的 App 侧边栏是唯一竖导航。
- 全程套用现有设计令牌（米色背景 / navy 主色 / 绿色可信度 / 玻璃质感），是现有风格的延续，不换配色。
- 资源内容走**现有的 /resource/* 接口**（讲义/视频/思维导图/图解/代码，S7 已真实化），不新增接口。

# 任务

## 1. 学习内容 → 插画卡片网格
把原来"学习内容"那一排平铺胶囊（定制讲义/讲解视频/思维导图/知识图解/代码实操）改成**响应式卡片网格**（`repeat(auto-fill,minmax(238px,1fr))`）。每张卡：
- 上半：**SVG 插画缩略图**（用下方【插画资源】里已确认的 5 个 SVG，原样做成组件，按资源类型映射）；
- 下半：标题 + 一句话描述；
- hover 上浮 + 阴影，active 轻微缩放。

## 2. 点击卡片 → 过场动画打开内容
- 用 **Framer Motion `layoutId` 共享元素动画**：点击卡片 → 缩略图平滑"长大"成详情视图头部、内容淡入；关闭（× / Esc / 点遮罩）原路收回。
- 详情视图渲染该资源的**真实内容**（调对应 /resource/* 接口）；详情头部背景沿用该卡的主题色，保持视觉连续。
- 遵守可访问性：Esc 关闭、焦点管理、遮罩可点关闭。

## 3. 分阶测试 → 独立主按钮（页面焦点）
- 把"分阶测试"从资源里**拎出来**，做成卡片网格下方一条醒目的绿色「去通关」主行（用现有绿色令牌）：标题"学完后来这里通关" + 一句说明 + 主按钮。
- 点击进入现有 quiz 组件（调既有 9.1 submit），**通过即驱动 Mastery 置 passed、点亮"已掌握"、推进进度**（复用既有逻辑，不新增掌握度路径）。

## 4. 辅助项降级
- 导学对话 / 资源推荐 / 重新生成 → 收成一行**小 chip**（次要工具行），不与内容卡争视觉权重。

## 5. 难度与溯源归位
- 难度自适应（入门/初级/高级）+ RAG 溯源信息 → 放进**「定制讲义」点开后的详情视图工具条/底部**（它们是针对讲义内容的操作），主网格保持干净。

# 约束
- 复用现有 quiz / 资源 Tab / 设计令牌 / 现有 Framer Motion 配置；不另造组件库。
- 不改后端、不改接口文档、不动有序学习模式。
- 移动端响应式（窄屏单列）；插画 SVG 用 viewBox 自适应。

# 验证（实测并说明）
1. 资源中枢模式显示 5 张**插画卡片**（非平铺胶囊），插画与示例风格一致；
2. 点击任意卡片 → **layoutId 过场动画**平滑打开，详情内容来自真实 /resource/* 接口，× / Esc / 点遮罩可关闭；
3. 「分阶测试」是独立绿色主按钮，进 quiz，**通过 → 已掌握点亮 + 进度推进**；
4. 导学对话/资源推荐/重新生成为次要小 chip；难度+溯源在讲义详情内；
5. 全程套用现有令牌、**未新增任何竖直导航**；
6. tsc --noEmit 干净、0 控制台错误、移动端正常。

# 输出
改动文件清单 + 6 项验证结果。完成即停。

# 插画资源（已确认风格，原样做成按类型映射的缩略图组件）

定制讲义（mint 底 #e7f4ee）：
```svg
<svg viewBox="0 0 220 170"><defs><filter id="s1" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#2b6e4f" flood-opacity="0.16"/></filter></defs><rect width="220" height="170" fill="#e7f4ee"/><g transform="rotate(-6 110 90)" filter="url(#s1)"><rect x="68" y="30" width="84" height="108" rx="10" fill="#fff"/><circle cx="86" cy="56" r="6" fill="#3a9d6e"/><rect x="100" y="52" width="40" height="7" rx="3.5" fill="#dfe8e2"/><circle cx="86" cy="80" r="6" fill="#3a9d6e"/><rect x="100" y="76" width="34" height="7" rx="3.5" fill="#dfe8e2"/><circle cx="86" cy="104" r="6" fill="#cfe5d8"/><rect x="100" y="100" width="40" height="7" rx="3.5" fill="#eef2ef"/></g><g transform="rotate(38 150 110)"><rect x="142" y="58" width="16" height="74" rx="4" fill="#46b07c"/><rect x="142" y="58" width="16" height="20" rx="4" fill="#2f9264"/><path d="M142 132 L150 148 L158 132 Z" fill="#f2d9a8"/><path d="M150 148 L150 138 L154 138 Z" fill="#2b2d3a"/></g><path d="M186 34 Q188 41 195 43 Q188 45 186 52 Q184 45 177 43 Q184 41 186 34Z" fill="#f0b94a"/></svg>
```
讲解视频（blue 底 #e8f0fb）：
```svg
<svg viewBox="0 0 220 170"><defs><filter id="s2"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#2d5aa0" flood-opacity="0.18"/></filter></defs><rect width="220" height="170" fill="#e8f0fb"/><g filter="url(#s2)"><rect x="48" y="40" width="124" height="80" rx="10" fill="#2b3a5c"/><rect x="56" y="48" width="108" height="64" rx="6" fill="#3d5180"/><circle cx="110" cy="80" r="20" fill="#fff"/><path d="M104 70 L122 80 L104 90 Z" fill="#3d5180"/><rect x="92" y="120" width="36" height="8" rx="4" fill="#2b3a5c"/><rect x="80" y="128" width="60" height="6" rx="3" fill="#b9c6dd"/></g><path d="M188 40 Q190 47 197 49 Q190 51 188 58 Q186 51 179 49 Q186 47 188 40Z" fill="#f0b94a"/></svg>
```
思维导图（lavender 底 #efeafb）：
```svg
<svg viewBox="0 0 220 170"><defs><filter id="s3"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#5b4ba8" flood-opacity="0.18"/></filter></defs><rect width="220" height="170" fill="#efeafb"/><path d="M96 60 H120 M96 110 H120 M120 60 V110 M120 85 H150" stroke="#b9a9e8" stroke-width="3" fill="none"/><g filter="url(#s3)"><rect x="40" y="46" width="52" height="30" rx="9" fill="#8b7bd6"/><rect x="40" y="96" width="52" height="30" rx="9" fill="#a99ae0"/><rect x="124" y="70" width="52" height="30" rx="9" fill="#7d6fce"/><rect x="150" y="40" width="40" height="24" rx="8" fill="#c3b6ec"/></g><circle cx="120" cy="60" r="5" fill="#f0b94a"/></svg>
```
知识图解（amber 底 #fbf2e2）：
```svg
<svg viewBox="0 0 220 170"><defs><filter id="s4"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#b5772a" flood-opacity="0.18"/></filter></defs><rect width="220" height="170" fill="#fbf2e2"/><g filter="url(#s4)"><rect x="42" y="44" width="78" height="82" rx="10" fill="#fff"/><rect x="56" y="98" width="12" height="18" rx="3" fill="#8b7bd6"/><rect x="74" y="84" width="12" height="32" rx="3" fill="#46b07c"/><rect x="92" y="72" width="12" height="44" rx="3" fill="#f0b94a"/></g><g filter="url(#s4)" transform="translate(150 92)"><circle r="28" fill="#fff"/><path d="M0 0 L0 -28 A28 28 0 0 1 24 14 Z" fill="#f0b94a"/><path d="M0 0 L24 14 A28 28 0 0 1 -20 19 Z" fill="#46b07c"/><circle r="12" fill="#fbf2e2"/></g></svg>
```
代码实操（slate 底 #eceef3）：
```svg
<svg viewBox="0 0 220 170"><defs><filter id="s5"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#1f2233" flood-opacity="0.22"/></filter></defs><rect width="220" height="170" fill="#eceef3"/><g filter="url(#s5)"><rect x="40" y="42" width="132" height="86" rx="10" fill="#2b2f42"/><circle cx="54" cy="56" r="4" fill="#ec6a5e"/><circle cx="68" cy="56" r="4" fill="#f0bd4a"/><circle cx="82" cy="56" r="4" fill="#46b07c"/><rect x="54" y="72" width="40" height="6" rx="3" fill="#5b6b8f"/><rect x="54" y="86" width="64" height="6" rx="3" fill="#46556f"/><rect x="54" y="100" width="30" height="6" rx="3" fill="#46556f"/><path d="M128 76 L118 90 L128 104 M150 76 L160 90 L150 104 M140 72 L138 108" stroke="#9fe0c0" stroke-width="3.5" fill="none" stroke-linecap="round"/></g><g transform="translate(160 110)" filter="url(#s5)"><circle r="18" fill="#46b07c"/><circle r="7" fill="#eceef3"/></g></svg>
```
> 插画颜色可微调以贴合令牌；但保持"浅底板 + 分层圆角 + 柔和色 + 星点"的统一风格。

═══════════════════════════════════════════════════════════════

## 给你（人）的提示
- 发 CC 时，可把 `card-illustration-system.html` 一并附给它做风格参照，效果更准。
- 重点盯验证 2、3：**过场动画真用了 layoutId（卡片"长大"而非简单弹窗）** + **分阶测试通过真驱动了已掌握/进度**。
- 若 CC 觉得 5 张插画里某张可优化，允许它在保持统一风格下微调，但别改成五花八门。
