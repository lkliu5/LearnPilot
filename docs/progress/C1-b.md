# C1-b 对话式学习画像诊断（后端实现）

> 契约依据：《后端接口文档.md》**第 17 章**（17.1 `/profile/dialogue`、17.2 StudentPortrait、17.3 `/profile/student-portrait`）。
> 范围：实现两个新接口及对话式诊断 Agent；**不动前端**（C1-c 独立会话）；**不改既有 30+ 接口签名**，尤其 `/profile/ability-portrait`（接口 7）保持原样，与新画像并存。

## 文件清单

### 新增（4 个）
- `backend/app/agents/dialogue_agent.py` —— `DialogueDiagnosticAgent`：多轮追问编排策略（按 6 维探查顺序，叠加「已问/已采集」推进，避免重复追问）+ 收敛判定；抽取经 `LLMClient`。
- `backend/app/services/student_portrait.py` —— StudentPortrait 持久化（get-or-create 空画像、按 key 字段级合并「随学随新」、维度稳定排序）+ 17.2/17.3 序列化。
- `backend/app/services/profile_dialogue.py` —— 会话 TTL（内存 30min，`d_` 前缀）+ SSE/JSON 双模式编排（复用 8.7/15.4 同款 `_sse_block` 流式封装；SSE 生成器在自有 DB 会话内完成读写）。
- `backend/tests/test_dialogue_profile.py` —— 11 条契约测试。

### 修改（5 个，均为增量，不动既有签名）
- `backend/app/models/entities.py` —— 新增 `StudentPortrait` 表（user_id PK / dimensions JSON / version / updated_at）。
- `backend/app/core/llm.py` —— 新增 `PORTRAIT_DIMENSIONS` 常量、`LLMClient.extract_portrait`（mock 确定性关键词抽取 + deepseek 真实抽取）、`_sanitize_portrait_updates`（key 白名单 / source 枚举 / inferred 低 confidence 防幻觉清洗）。既有方法逐字未动。
- `backend/app/api/v1/profile.py` —— 新增 `POST /profile/dialogue`（SSE/JSON 双模式）、`GET /profile/student-portrait`。既有 4 个端点未动。
- `backend/app/schemas/profile.py` —— 新增 `DialogueRequest`。
- `backend/app/core/init_db.py` —— import 列表补 `StudentPortrait`（create_all 自动建新表，无需迁移）。

## 启动 / 验证命令

```bash
# 启动（mock 无密钥即可跑通；.env 配 deepseek+key 则走真实模式）
cd backend && uvicorn app.main:app --reload --port 8000
# 强制 mock：LLM_PROVIDER=mock uvicorn app.main:app --port 8000

# 测试
cd backend && pytest -q                                  # 全量
cd backend && pytest tests/test_dialogue_profile.py -q   # 本阶段
```

## 验证实测结果（0 报错）

### 1. pytest

```
# 本阶段
11 passed, 1 warning in 3.67s
# 全量回归（含 test_contract_snapshot 既有 30+ 接口契约快照）
126 passed, 1 skipped, 1 warning in 29.00s
```

### 2. 多轮对话（JSON 非流式，真实 DeepSeek 模式 live HTTP :8012）

诊断前空画像 → `{"dimensions": [], "version": "v1", "updatedAt": "..."}`（17.3 占位，不报错）。
逐轮追问推进、`portraitUpdates` 累积、`diagnosisComplete` 在采集到 5 维时翻 true：

```
轮1 学生:我是计算机本科，做过Python爬虫
    AI:了解了。这次学习你最想达成的目标是什么？
    抽取:[('prior_experience','计算机本科，有Python爬虫经验','dialogue',1.0),
          ('knowledge_base','计算机本科，Python爬虫','inferred',0.6)]  done=False
轮2 学生:想转大模型应用工程师 → 抽取 learning_goal(0.9)  done=False
轮3 学生:我喜欢边写代码边学，动手型 → 抽取 cognitive_style(0.8)  done=False
轮4 学生:时间比较紧张 → 抽取 learning_pace(inferred,0.5)  done=True   # 满 5 维收敛
轮5 学生:概念容易记混 → 抽取 error_preference(0.8)  done=True
轮6 学生:学习节奏想稳一点 → learning_pace 原地更新为「希望稳定」(0.8)  # 随学随新

GET /profile/student-portrait → version=v1 维度数=6（6 维齐全，含 updatedAt）
```

### 3. SSE 流式（`Accept: text/event-stream`，对齐 17.1）

```
Content-Type: text/event-stream; charset=utf-8
data: {"delta": "了解了。"}

data: {"delta": "先了解一下你的基础——相关课程你学过哪些，掌握到什么程度？"}

event: portrait
data: {"updates": [{"key":"prior_experience",...,"source":"dialogue"},
                   {"key":"learning_goal",...,"source":"dialogue"}]}

event: done
data: {"sessionId":"d_40edb48b51","suggestions":[...],"diagnosisComplete":false}
```

### 4. Mock 与真实双模式（结构契约一致）

- **真实 DeepSeek**（live :8012，见上）：抽取贴合学生原话、source/confidence 由模型给出，inferred 维度 confidence 被清洗到 ≤0.6。
- **Mock**（`LLM_PROVIDER=mock` live :8014，无密钥）：确定性关键词抽取（如 `有Python工程实践(爬虫)`/`一般` score 65/`偏实践/动手型`），响应键集合与 deepseek 完全一致 `{sessionId, reply, portraitUpdates, suggestions, diagnosisComplete}`。deepseek 错误（如无 Key）经 `LLMGenerationError → code 2001 / HTTP 500`（pytest 覆盖）。

### 5. 回归：`/profile/ability-portrait`（接口 7）逐字未变

```
GET /api/v1/profile/ability-portrait →
{"dimensions":["机器学习基础","神经网络","深度学习","注意力机制","Transformer","大模型微调"],
 "values":[85,72,68,45,30,20]}
```
异质学生画像（StudentPortrait）为**新增并存结构**，独立存储、独立维度集，未与知识点雷达合并或替换。`test_contract_snapshot` 全量通过佐证既有接口契约稳定。

## 防幻觉口径（17.1）

- 无法从对话判断的维度不编造（无信号不下发 update）；
- `source ∈ dialogue | manual | inferred`：对话明确陈述 = dialogue，首轮 `context` 表单显式信息 = manual，间接推断 = inferred；
- `inferred` 维度 confidence 统一清洗到 ≤ 0.6；
- key 仅接受固定 6 维白名单，模型给出的越界 key 一律丢弃（`_sanitize_portrait_updates`）。

## 备注 / 后续
- 会话上下文为进程内存 TTL（30min），生产替换 Redis（路径写 README，未在 demo 实现）。
- 「随学随新」当前由对话写入；测验/讲义学习回写对应维度（如 knowledge_base.score）为后续闭环点，本阶段已预留 `apply_updates` 字段级合并能力。
- 前端对话式诊断页改造为 C1-c 独立会话。
