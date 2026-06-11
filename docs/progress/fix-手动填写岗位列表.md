# fix — 画像诊断「手动填写」目标岗位选择器为空 · 修复总结

> 类型：缺陷修复（短会话）｜状态：✅ 完成（0 报错）｜日期：2026-06-11
> 现象：手动填写模式下目标岗位无可选项；在线 / 离线（JOB_MARKET_OFFLINE=true）两模式均存在。

## 1. 根因定位（要求 1，逐问回答）

**① 手动填写路径的岗位列表数据源是否接了 GET /job-market/hot？**
是。手动填写与材料上传**共用** Step1 采集页同一个 `JobMarketPanel`（页面本就只有这一个
选择器），其热门岗位列表联调-P1 已接 `getHotJobs()` → `GET /job-market/hot`——数据源
本身是统一的，问题不在"没接"。

**② 该调用对 code:2002 是否与快照接口同样走 okCodes 白名单？**
**否**。`getHotJobs` 用裸 `apiGet`（无 `okCodes:[2002]`），与快照接口
`getJobMarket`（有白名单）口径不一致——hot 一旦按第 5 章降级约定回 2002+数据，
会被当错误抛掉。（注：当前后端 `hot_jobs` service 不看离线开关、恒回 code 0，
两模式实测均 4 岗——所以 2002 不是本缺陷的触发点，但契约上必须补齐。）

**③ 实际触发「列表为空且两模式均现」的缺陷链**：
`JobMarketPanel` 联调 effect 拿到 hot 结果后**无条件覆盖**预置初值——
当后端 hot **成功返回空列表**（`job_snapshots` 表无数据：新建库种子未跑/导入失败，
评审机常见状态）时，`setHotJobs([])` 把预置 4 岗初值覆盖为空 → 选择器空、
无岗位可选；且该路径 code 0 无任何报错（与「Console 无报错」实证吻合），
hot 又不看 `JOB_MARKET_OFFLINE` 开关 → **在线/离线表现完全一致**（与「两模式均存在」
实证吻合）。空列表与请求失败两条退路均无预置兜底、无离线标记。

> 旁证：本机 `backend/.env` 即 `JOB_MARKET_OFFLINE=true`，8000 实例快照接口实测
> code 2002——排查时的"离线模式"即此开关。

## 2. 修复方案（要求 2）

**统一数据源 + 永不为空的降级链**（`getHotJobs` 升级为与 5.2 快照同口径的降级语义，
两条路径共用的选择器吃同一结果）：

| hot 返回 | 列表 | offline |
|---|---|---|
| code 0 + 非空列表 | 后端列表 | false |
| code 2002（okCodes 放行，对齐快照接口白名单） | 后端列表 | true |
| **code 0 + 空列表**（数据源无快照——本缺陷场景） | **预置 4 岗** | **true** |
| 请求失败（网络/异常） | **预置 4 岗** | **true** |
| mock 模式 | 内置 HOT_JOBS | false |

- 返回类型 `HotJob[]` → `HotJobsResult { jobs, offline }`，offline 沿用既有「离线」
  语义（与 `JobMarketResult.offline` 同口径），不新增状态概念；
- **页级标签跟随 offline**（顺手项）：`JobMarketPanel` 新增可选回调
  `onOffline?`（热门列表降级 或 当前快照降级，任一为真即离线），ProfileBuilder
  右上角徽章文案动态化：离线 → `离线快照 · 预置库`，正常 → `联网快照 · 缓存`
  （同一 span/同一样式类，仅文案随数据源状态变化）。

## 3. 改动文件清单（均限 services 与数据请求层，UI 结构零改动）

| 文件 | 改动 |
|---|---|
| `src/services/api.ts` | 拆出 `apiRequestWithCode`（返回 `{code, data}`，供需感知降级码的调用方）；`apiRequest` 委托之，对既有调用方零影响。 |
| `src/services/jobMarket.ts` | `getHotJobs` 降级语义（上表）：okCodes 2002 + 空列表/失败 → 预置 4 岗兜底 + offline。 |
| `src/components/JobMarketPanel.tsx` | 消费 `HotJobsResult`（`hotOffline` state）；新增可选 `onOffline` 回调上抛页级离线状态。chips/搜索/快照卡结构零改。 |
| `src/pages/ProfileBuilder.tsx` | 页级徽章文案跟随 `jobOffline`（由 onOffline 上抛）；其余零改。 |
| `backend/scripts/verify_fix_hot_jobs.py` | **新增**：在线/离线两模式 hot+snapshot 回包实测脚本。 |
| `backend/scripts/verify_fix_manual_finish.py` | **新增**：手动填写收尾等价请求（diagnosis-complete → journey 回读）实测脚本。 |

## 4. 验证（要求 3，0 报错）

### ① 类型检查
```
npx tsc --noEmit -p tsconfig.json   →  EXIT 0
```

### ② 在线(8002, JOB_MARKET_OFFLINE=false) / 离线(8000, =true) 两模式实测
```
[hot  :8002] http=200 code=0 offline=False n=4 ids=['llm-app','algo-engineer','ml-engineer','data-analyst']
[snap :8002] http=200 code=0    offline=None
[hot  :8000] http=200 code=0 offline=False n=4 ids=['llm-app','algo-engineer','ml-engineer','data-analyst']
[snap :8000] http=200 code=2002 offline=True
```
- 两模式 hot 均 4 岗 → 选择器有岗可选；修复后即使该接口回空/失败，前端也回落
  预置 4 岗 + 离线标记（缺陷场景的兜底路径经 tsc 两分支编译覆盖）。

### ③ 手动填写完成诊断（两模式收尾等价请求）
```
[finish :8002] diagnosis-complete code 0 hasDiagnosed=True -> journey.targetJob=大模型应用工程师 matchPct=33
[finish :8000] diagnosis-complete code 0 hasDiagnosed=True -> journey.targetJob=大模型应用工程师 matchPct=33
```
选岗 → 手动填写 → 确认 → 对标 → 完成诊断 全链路后端调用两模式均 code 0。

### ④ Vite transform
```
GET /src/services/api.ts / jobMarket.ts / JobMarketPanel.tsx / ProfileBuilder.tsx → 全部 200
```

### ⑤ 诚实声明
- 无浏览器自动化工具，「两模式下手动填写点选岗位」未做 DOM 级断言；已覆盖其全部
  确定性环节：数据源（两模式 hot 实测）、降级链（空/失败/2002 → 预置兜底，类型层
  覆盖）、收尾调用（diagnosis-complete 两模式 code 0）。建议手动走查：画像诊断页
  选一个岗位 chip → 点「跳过上传，手动填写」→ 填写三项 → 对标页应显示该岗位
  对标与匹配度 → 完成诊断。
- 「job_snapshots 表为空」的缺陷原场景未在本机直接复现（本机库已种子）——根因为
  代码审读结论（空数组覆盖预置初值），其兜底分支由降级链保证；如需实地复现可
  清空该表后走查。
- 后端 `hot_jobs` 当前在离线开关下不降级（恒 code 0）——okCodes 白名单为契约对齐
  的前向兼容项；若后续后端给 hot 补 2002 语义，前端无需再改。
