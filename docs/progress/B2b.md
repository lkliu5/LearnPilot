# B2-b — P0 主流程后半（Mastery/Journey + Resource + Quiz）· 完成总结

> 阶段：B2 后半（B2-b）｜状态：✅ 完成（0 报错）｜日期：2026-06-10
> 范围：B2 共 15 接口，本次完成后半 **8 个接口**（12/13/14/15/16/17/23/24）。
> 至此 B2（P0 主流程 15 接口）全部立起，前端可全面切真实 API。

## 1. 交付内容

### Mastery & Journey（接口文档第 7 章，接口 12–15）
- `GET /mastery`：掌握度全集 `{ status: Record<kpId,KPStatus> }`，未出现的知识点视为未开始。
- `POST /mastery/{kpId}/check`：去检验。`learning`（及未开始）→ `pending-check`；
  **已 `passed` 保持不变**（实测验证）。
- `POST /mastery/{kpId}/pass`：标记通过，**幂等**（重复调用仍 `passed`）。
- `GET /journey`：旅程状态，`currentStep` 按接口文档 7.4 规则后端推导——
  未诊断→`diagnose`；已诊断未生成路径→`generate-path`；**全部 6 核心知识点 `passed`**→`review`；
  否则→`learn`（与前端 `getJourneyStep` 一致；「全部课程完成」以核心知识点全 passed 推导，
  因前端学习路径/图谱均由掌握度派生）。

### Resource（接口文档第 8 章，接口 16/17）
- `GET /resource/knowledge-point/{kpId}`：知识点元信息 `{ id, name, description, status }`，
  `status` 取自掌握度（未开始默认 `learning`，与前端资源页初始一致）。知识点不存在→`1004`。
- `POST /resource/lecture`：自适应讲义。经 `LLMClient.generate_lecture`（mock）按
  **入门/初级/高级 3 档**确定性产出 `markdown`（初级/高级含 ```python``` 代码块）+
  `sources`（3 条，type∈教材/课程/文档，confidence 0-1）+ `hallucinationRate`（0.021，前端显示 <5%）。
  生成讲义同时把该知识点置为 `learning`；结果写 `ResourceCache`（kp+difficulty+kind 唯一），
  同档命中缓存直接返回（不重复再生成）。难度档非法→`1001`；知识点不存在→`1004`。

### Quiz（接口文档 9.1，接口 23/24）
- `GET /quiz/{kpId}`：返回种子 `QuizQuestion[]`（含 `correct_answer`/`explanation`，契约 2.5 要求）。
  知识点不存在→`1004`。
- `POST /quiz/{kpId}/submit`：判分。`single/boolean` 直接比较，`multiple` 集合相等（顺序无关）；
  `score = 答对数/总题数×100`（四舍五入），`passed = score≥60`。**≥60 联动掌握度置 `passed`**
  并返回 `masteryUpdated`；未通过 `masteryUpdated=null`，`wrong[]` 填充答错题（驱动错题强化）。

### 状态枚举
全程严格使用 `learning / pending-check / passed`（连字符，无下划线），统一定义于
`app/services/mastery.py` 常量，避免漂移。

所有响应套统一信封 `{code,message,data,traceId}`；受保护接口均经 `get_current_user`。
生成调用统一经 `LLMClient`（CLAUDE.md 纪律），B5 替换为真实 RAG+Agent，签名不变。

## 2. 文件清单

新文件 7 个（≤8）；改动既有文件 3 个。

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/app/schemas/resource.py` | 新增 | LectureRequest / QuizSubmitRequest 请求体校验 |
| `backend/app/services/mastery.py` | 新增 | 掌握度读写（check/pass/ensure_learning）+ journey currentStep 推导 + 状态枚举常量 |
| `backend/app/services/resource.py` | 新增 | 知识点元信息 + 讲义生成（经 LLMClient，写 ResourceCache 缓存） |
| `backend/app/services/quiz.py` | 新增 | 测验题读取 + 判分 + ≥60 联动掌握度 |
| `backend/app/api/v1/mastery.py` | 新增 | 接口 12/13/14/15（含 GET /journey） |
| `backend/app/api/v1/resource.py` | 新增 | 接口 16/17 |
| `backend/app/api/v1/quiz.py` | 新增 | 接口 23/24 |
| `backend/app/core/llm.py` | 改动 | 新增 `generate_lecture()` + 难度档/讲义来源/幻觉率常量（mock 确定性产出） |
| `backend/app/core/init_db.py` | 改动 | 新增 6 核心知识点各 3 道种子测验题（nn 三题与前端逐字对齐），幂等灌入 |
| `backend/app/main.py` | 改动 | 挂载 mastery / resource / quiz 三路由 |

> 设计取舍：
> - `GET /journey` 归入 mastery 路由（接口文档同属第 7 章），使新文件维持 7 个。
> - `check` 对「未开始」也置 `pending-check`（与前端 `goCheck` 一致：非 passed 即 pending-check）；
>   `passed` 永不回退。
> - 讲义写 `ResourceCache` 体现「同档不重复再生成」；B5 真实生成沿用同一缓存键。
> - `hallucinationRate` mock 固定 0.021；B5 替换为接口文档 15.3 逐句接地校验口径。

## 3. 启动 / 验证命令

```bash
cd backend
uvicorn app.main:app --reload --port 8000      # 首次启动自动幂等灌入种子测验题
```

> 注：本阶段无新增依赖（沿用 B2-a 的 requirements.txt）。

## 4. 验证实测（0 报错）

> 登录 `learner_001/123456` 取 token；全部经统一信封返回。

### ① 完整闭环：lecture(三档) → quiz → 提交全对 → mastery passed → journey 推进

```
LOGIN 200  role=learner
诊断+生成后 journey.currentStep = learn

LECTURE[入门] kpId=nn difficulty=入门  md="# 神经网络基础（入门版）"  sources=3  hallucinationRate=0.021
LECTURE[初级] kpId=nn difficulty=初级  md="# 神经网络基础（初级版）"  sources=3  hallucinationRate=0.021
LECTURE[高级] kpId=nn difficulty=高级  md="# 神经网络基础（高级版）"  sources=3  hallucinationRate=0.021

KP-META  {id:nn, name:神经网络基础, description:..., status:learning}
MASTERY(讲义后)  {nn: learning}            # 生成讲义触发 learning
CHECK nn         {id:nn, status:pending-check}   # learning → pending-check

QUIZ get  count=3  ids=[nn_q1, nn_q2, nn_q3]
SUBMIT(全对)  score=100  passed=True  correctCount=3  total=3  wrong=0
              masteryUpdated={id:nn, status:passed}

MASTERY(通过后)  {nn: passed}              # 提交全对自动置 passed
JOURNEY(通过后)  currentStep = learn        # 单点通过；review 需全部 6 核心 passed
```

### ② 判分 / 联动 / 边界（全部符合契约）

```
错答 submit(ml)     score=0   passed=False  masteryUpdated=null  wrong=3
部分对 submit(dl)   score=33  passed=False  correctCount=1/3            # 四舍五入
pass 幂等(cnn)      两次均 {id:cnn, status:passed}
check-on-passed     {id:cnn, status:passed}     # 已通过保持不变
全部 6 核心 pass 后  journey.currentStep = review
                    mastery = {ml,nn,dl,cnn,transformer,finetune 均 passed}

unknown quiz          http=404 code=1004
unknown kp-meta       http=404 code=1004
讲义非法难度(中级)     http=400 code=1001  "难度档非法，应为 入门|初级|高级"
讲义 unknown kp        http=404 code=1004
无 token 访问 mastery  http=401 code=1002
```

## 5. 边界确认 / 给后续阶段的约定

- B2（15 接口）至此全部完成；前端可全面切真实 API（最早联调点）。
- 前端 `src/` 业务逻辑 / store / 路由零改动。
- 掌握度后端为权威源；`journey.currentStep` 完全由后端按 7.4 推导，前端 Zustand 退化为缓存。
- 讲义 `sources` / `hallucinationRate` 为 mock 占位；B5 接入「RAG 检索→生成 Agent→审核 Agent」，
  `generate_lecture` 方法签名与响应契约不变，仅替换实现并按 15.3 计算真实幻觉率。
- 测验题为 DB 种子（6 KP×3 题，nn 与前端逐字对齐）；B5/B6 可由生成 Agent 动态产题，接口不变。
- 掌握度为 SQLite 持久化（与 B1 同库）；进程重启不丢失。
