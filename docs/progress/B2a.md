# B2-a — P0 主流程前半（Profile + LearningPath + 异步任务）· 完成总结

> 阶段：B2 前半（B2-a）｜状态：✅ 完成（0 报错）｜日期：2026-06-10
> 范围：B2 共 15 接口，本次只做前半 **7 个接口** + LLM 适配层 + 异步任务基建；
> 后半（Mastery/Journey/Resource/Quiz，接口 12–17/23/24）留待 B2-b。

## 1. 交付内容

- **LLMClient 适配层**（`app/core/llm.py`）：`provider=mock` 落地，确定性产出 6 维技能
  画像与两段式叙述；`deepseek/qwen/anthropic` 留接口占位（抛 `NotImplementedError`，
  B5 接入真实生成 + RAG）。**后续所有生成类接口必须经本层调用**（CLAUDE.md 工程纪律）。
- **异步任务基建**（`app/core/tasks.py`）：进程内任务表 + 状态机
  `pending→running→succeeded/failed` + `submit()` 后台调度 + `to_data()` 转接口
  文档 15.2 响应结构（`{taskId,status,progress?,result?,error?}`）。
- **Profile 四接口**（接口文档第 4 章）：
  - `POST /profile/parse`（multipart）：pypdf 抽 PDF / 解码 txt/md → MockLLM 输出固定
    6 维 skills；**无任何材料时 source=manual，不编造经历**（防幻觉约束）。
  - `POST /profile/narrative`：经 MockLLM 拼两段带 `sourceId` 叙述；**无材料返回 `data:null`**
    （与前端 `generateNarrative` 无材料返回 null 一致）。
  - `POST /profile/diagnosis-complete`：写 Journey（`hasDiagnosed/targetJobName/matchPct`）。
  - `GET /profile/ability-portrait`：返回 6 维雷达，以最近一次 parse 结果为准（内存缓存），
    无则基线默认。
- **LearningPath 两接口**（接口文档第 6 章）：
  - `GET /learning-path`：DB 种子 6 课 + milestones（按旅程/进度实时推导）+ summary
    （`overallProgress = sum(progress)/课程数`，实测 44，与文档示例一致）。
  - `POST /learning-path/generate`：异步 `taskId`，Mock 1.5s 完成后写 `hasGeneratedPath=true`，
    任务 `result = {lessons:[...]}`。
- **通用任务接口**：`GET /tasks/{taskId}`（接口文档 30 + 15.2），未知任务 → `code 1004 / 404`。

所有响应套统一信封 `{code,message,data,traceId}`；受保护接口均注入 `get_current_user`。

## 2. 文件清单

实质新文件 7 个 + 包标记 1 个；改动既有文件 2 个。

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/app/core/llm.py` | 新增 | LLMClient 适配层（mock 实现 + 3 provider 占位）；6 维固定键名常量 |
| `backend/app/core/tasks.py` | 新增 | 内存异步任务表 + 状态机 + `submit()` + `Task.to_data()` |
| `backend/app/schemas/profile.py` | 新增 | Narrative/DiagnosisComplete/GeneratePath 等请求体校验（camelCase 对齐契约） |
| `backend/app/services/profile.py` | 新增 | 画像服务：parse（文本抽取+MockLLM）/narrative/diagnosis/ability-portrait |
| `backend/app/api/v1/profile.py` | 新增 | 接口 4/5/6/7 |
| `backend/app/api/v1/learning_path.py` | 新增 | 接口 10/11 + 路径 summary/milestones 推导 + 异步生成 worker |
| `backend/app/api/v1/tasks.py` | 新增 | 接口 30：`GET /tasks/{taskId}` |
| `backend/app/services/__init__.py` | 新增 | services 包标记 |
| `backend/app/main.py` | 改动 | 挂载 profile / learning_path / tasks 三路由 |
| `backend/requirements.txt` | 改动 | 追加 `python-multipart`、`pypdf`（multipart 表单 + PDF 抽取） |

> 设计取舍：
> - LLMClient 采用语义化方法（`parse_skills`/`generate_narrative`）而非裸 `complete()`，
>   因各接口需返回与契约逐字对齐的结构化数据；B5 替换实现时方法签名不变。
> - 最近画像按 userId 存进程内存（轻量栈，对齐「内存 TTL 会话」取向），使
>   parse → ability-portrait 链路一致；生产替换会话存储。
> - 异步 worker 内自管理 `SessionLocal`（不复用请求级 Session），避免请求结束后会话关闭。

## 3. 启动 / 验证命令

```bash
cd backend
pip install -r requirements.txt          # 新增 python-multipart / pypdf
uvicorn app.main:app --reload --port 8000
```

## 4. 验证实测（0 报错）

> 注：含中文的 JSON 请求体经文件 `--data-binary @file` 提交（避免 shell 内联编码问题），
> 接口本身 UTF-8 正常。

### ① 全链路闭环：parse → narrative → diagnosis → ability-portrait → generate → 轮询 → learning-path

```
# 登录 learner_001/123456 拿 token

# parse（带 resume.txt + 背景描述）→ source=resume，命中关键词的维度抬升
skills: 机器学习基础93 / 神经网络72 / 深度学习76 / 注意力机制45 / Transformer38 / 大模型微调36
materials: [{m1, resume.txt, doc}, {m2, 背景描述, text}]

# narrative（带 materials）→ 恰好两段，key/weak 着色，sourceId=m1
paragraphs[0]: 该学习者具备 [人工智能·key·m1] 专业背景，[机器学习基础能力突出·key·m1]。
paragraphs[1]: 与目标岗位「大模型应用工程师」相比，[大模型微调能力偏弱·weak]，建议…
sources:[{m1,...}]  materialCount:1

# diagnosis-complete → {"hasDiagnosed": true}

# ability-portrait → 反映最近 parse
{"dimensions":[6维],"values":[93,72,76,45,38,36]}

# learning-path/generate → {"taskId":"t_6a4511266228"}
# 轮询 GET /tasks/{id}:  running → running → succeeded
succeeded.result = {"lessons":[6课]}   progress:100

# learning-path summary（诊断+生成后）
summary: {completedCount:2, inProgressCount:1, overallProgress:44}
milestones: 完成画像诊断✓(2026-05-20) / 生成学习路径✓(2026-05-22) /
            完成基础课程✓(2026-05-28) / 掌握核心架构✗
```

### ② 防幻觉 / 边界

```
# parse 无任何材料 → 全部 skills source=manual，materials=[]（不编造）
sources: {'manual'} | materials: []

# narrative 无材料 → data 为 null（不编造叙述）
{"code":0,"message":"ok","data":null,...}

# tasks 未知 id → code 1004 / HTTP 404
http=404 code=1004

# 受保护接口无 token → code 1002 / HTTP 401
http=401 code=1002
```

## 5. 边界确认 / 给后续阶段的约定

- 仅完成 B2-a（7 接口 + LLM 适配层 + 异步任务）；**B2-b** 待做：`GET /mastery`、
  `POST /mastery/{kpId}/check|pass`、`GET /journey`（currentStep 推导）、
  `GET /resource/knowledge-point/{kpId}`、`POST /resource/lecture`、`GET /quiz/{kpId}`、
  `POST /quiz/{kpId}/submit`。本阶段未实现 `/journey`（轮询时返回 404 属预期）。
- 前端 `src/` 业务逻辑 / store / 路由零改动。
- 生成类接口已统一经 `LLMClient`；B5 仅替换 `provider` 实现与 service 内生成逻辑，
  接口签名与响应契约不变。
- 异步任务表为进程内存实现，重启即清空；生产替换 Redis/Celery（路径写 README）。
