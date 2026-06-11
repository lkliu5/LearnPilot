# B5-b — 真实生成替换（RAG → 生成 Agent → 审核 Agent + deepseek provider）· 完成总结

> 阶段：B5 后半（B5-b）｜状态：✅ 完成（0 报错）｜日期：2026-06-11
> 范围：`/resource/lecture`、`/profile/parse`、`/profile/narrative` 三接口的真实生成替换
> + deepseek provider 接入 + 15.3 幻觉率逐句接地口径落地。
> **三接口签名与响应字段零改动；llm_provider=mock 时行为与 B2 逐字等价（前端演示兜底不破坏）。**

## 1. 交付内容

### ① /resource/lecture 真实生成（接口文档 8.2）

`services/resource.generate_lecture` 按 provider 分支：

- **mock**：原 B2 路径原样保留（`LLMClient.generate_lecture` 确定性产出，缓存 kind=`lecture` 不变）；
- **真实模式**：复用 B5-a 的 `run_learning_workflow`，注入真实检索器
  `_retrieve_for_lecture`（B3 `HybridRetriever.search` 候选池 8 → `Reranker.rerank` top-4），
  工作流拓扑与 trace 结构零改动（每次真实生成落一行 `WorkflowTrace`，B7 直接消费）：
  - `sources`：检索 chunk 按文档去重回填——`document_title · source_location` → title、
    文档 `category`（白名单 教材|论文|文档|课程 外回落「文档」）→ type、
    该文档最高重排分（0-1 截断，重排降级时为 RRF 归一化分）→ confidence；
  - `hallucinationRate`：critic 真实实现按 **15.3 口径**计算（见 ③）；
  - 缓存 kind 带 provider 后缀（`lecture@deepseek`），与 mock 缓存互不污染，切 provider 演示数据不串。

### ② /profile/parse 与 /profile/narrative 真实抽取/叙述（接口文档 4.1/4.2）

- `LLMClient.extract_profile(text, source)`：mock 或**无材料文本**（manual）时确定性产出
  （与 B2 逐字等价；防幻觉约束——无材料不调用 LLM 编造经历）；deepseek 时真实抽取 + 契约清洗：
  education/major/goal 枚举白名单（非法值回落「其他」）、skills 固定 6 维补齐
  （材料未体现的维度落基线值）、level 截断 0-100、source 统一为调用方判定值。
- `LLMClient.generate_narrative` deepseek 分支：真实两段叙述 + 契约清洗——
  恰好两段（不足补确定性差距段）、**sourceId 只能取材料 id 白名单，列表外一律置 null**
  （与 4.2 契约一致，防幻觉引用）、tone 仅保留 key|weak。

### ③ critic 真实实现：15.3 逐句接地（`app/rag/grounding.py`）

- 生成内容按句切分（**代码块整体剔除**、Markdown 语法符号剥离、<6 字符短句过滤），
  每句与来源切片（切片全文 + 切片内逐句，细粒度提升长切片保真）做 embedding 余弦相似度取最大值；
  低于阈值（`settings.grounding_threshold`）→ 未接地，`hallucinationRate = 未接地句数/总句数`；
  **无任何 RAG 来源（纯模板/兜底）→ 按 15.3 约定置 0**。
- `critic_agent` 真实模式**不经 LLM**：本地接地计算，`validationScore = 1 - hallucinationRate`，
  issues 列出未接地句（≤5 条，作为重试反馈注入 generator）；prompt 仍现读模板渲染并记录
  （trace.promptExcerpt / 热更新验证不受影响）。mock 路径（含 `set_force_critic_low` 钩子）原样保留。
- **阈值标定**：接口文档默认 0.75 保留为 config 默认值；bge-small-zh 实测逐句相似度中位数
  ≈0.73（接地句多落 0.6-0.9），0.75 会把 62% 真实接地句误判，故按 15.3「阈值可在配置中调整」
  在 `backend/.env` 设 `GROUNDING_THRESHOLD=0.6`（实测 rate 0.08-0.19，一次通过零重试）。

### ④ deepseek provider（`app/core/llm_deepseek.py`）

- openai 兼容 SDK（`OpenAI(base_url=api.deepseek.com)`），`DEEPSEEK_API_KEY` 读
  `backend/.env`；超时（`LLM_TIMEOUT_SECONDS`，默认 60s）与一切上游异常统一包装
  `LLMGenerationError` → 三接口路由映射 **code 2001 / HTTP 500**（接口文档 1.3）。
- 连接加固：api.deepseek.com 多 A 记录中个别 IP 偶发 TLS 重置（httpx 默认单连接直接失败，
  curl 因多 IP 回退成功），SDK 配 `httpx.HTTPTransport(retries=2)` 连接级换址重试，实测稳定。
- `LLMClient.complete()` 真实路由：generation → 渲染后 prompt 直发（剥 ``` 围栏）；
  diagnosis → JSON 约束输出 + 容错解析（非 JSON 时自由文本兜底，不中断工作流）；
  critic → 不走 LLM 通道（见 ③）。JSON 提取 `_extract_json` 对「JSON 外包裹说明文字」容错。

## 2. 文件清单

新增 5 个（≤8 上限）：

| 文件 | 说明 |
|---|---|
| `backend/app/core/llm_deepseek.py` | DeepSeek openai 兼容调用 + LLMGenerationError + 连接重试 |
| `backend/app/rag/grounding.py` | 15.3 逐句接地校验（句切分/代码块剔除/相似度判定） |
| `backend/tests/test_b5b.py` | 16 条契约测试（TDD：先实测 RED 再实现转绿；deepseek 路径全 monkeypatch，无 Key 可跑） |
| `backend/tests/conftest.py` | 测试会话强制 mock 基线（防 .env 真实 Key 让测试走付费调用） |
| `docs/progress/B5b.md` | 本总结 |

既有文件改动：

| 文件 | 改动 |
|---|---|
| `backend/app/core/config.py` | deepseek 四配置 + llm_temperature + grounding_threshold(默认 0.75) |
| `backend/app/core/llm.py` | deepseek 分支（complete/extract_profile/narrative 清洗）+ JSON 容错 + LLMGenerationError re-export；mock 路径逐字保留 |
| `backend/app/agents/critic_agent.py` | 真实模式走 15.3 本地接地（mock 路径不变） |
| `backend/app/services/resource.py` | lecture 真实分支（工作流+真实检索）+ sources 映射 + provider 隔离缓存 |
| `backend/app/services/profile.py` | parse 改走 extract_profile（education/major/goal 真实抽取） |
| `backend/app/api/v1/resource.py` `profile.py` | LLMGenerationError → 2001/500 映射 |
| `backend/requirements.txt` | 追加 `openai` |

**未触碰**：`frontend/src`（零文件改动）、接口路径/字段/枚举、B5-a 工作流拓扑与 trace 结构。

## 3. 启动 / 验证命令

```bash
cd backend && pip install -r requirements.txt      # 新增 openai
cd backend && python -m pytest tests/ -q           # 与 .env 无关，强制 mock 基线
# mock 模式（无 Key）：.env 不配或 LLM_PROVIDER=mock
# 真实模式：backend/.env → LLM_PROVIDER=deepseek + DEEPSEEK_API_KEY=sk-xxx + GROUNDING_THRESHOLD=0.6
cd backend && uvicorn app.main:app --port 8000
```

## 4. 验证实测（0 报错）

### ① pytest（TDD：先 RED——14 条因缺模块/方法失败，实现后全绿）

```
$ python -m pytest tests/ -q
39 passed, 1 skipped in 42.80s    （16 条 B5-b 新增 + 24 条既有；skip 为「无 Key」用例在有 Key 环境的预期跳过）
```

> 注：套件含 torch 首次加载时 Windows faulthandler 打印的一段已处理 access-violation 堆栈，
> 为 torch-on-Windows 已知噪声（`python -c "import torch"` 正常、退出码 0），非测试失败。

### ② mock / 真实双模式回包对比（curl 实测，POST /api/v1/resource/lecture，kpId=nn）

| | mock（LLM_PROVIDER=mock） | 真实（deepseek） |
|---|---|---|
| markdown | 确定性模板讲义 422 字符，`# 神经网络基础（初级版）…`（三档逐字与 B2 一致，pytest 逐字断言） | 真实生成 2025 字符，`# 神经网络基础讲义 / ## 1. 神经元：神经网络的基本计算单元…` |
| sources | B2 占位常量：`《深度学习》(花书) 相关章节/教材/0.92` 等 3 条 | 真实检索回填：`01-神经网络与反向传播 · 神经网络基础与反向传播算法 / 段落 1（教材, 0.7）`、`03-机器学习基础与大模型微调 · …（教材, 0.51）` |
| hallucinationRate | 0.021（占位常量） | **0.0816**（15.3 逐句接地实算；高级档实测 0.1875） |
| 工作流 | 不触发 | `wf_88c90a179405`：diagnosis 5.1s → rag 29.3s → generation 11.7s → critic 2.0s，**success / retry=0**，trace 持久化 |

mock 三档 curl 均 `code:0` 且与 B2 逐字一致（`入门|初级|高级` 实测）；前端零改动无回归。

### ③ 真实模式 parse / narrative（curl 实测）

- `POST /profile/parse` 上传 txt（硕士/人工智能/ML+Transformer 项目经历）→
  `education=硕士, major=人工智能, goal=职业培训（均 source=resume）`；
  skills：机器学习基础 70 / 神经网络 72 / 深度学习 70 / 注意力机制 60 / Transformer 60 /
  **大模型微调 20（材料未提及 → 落基线不编造）**——抽取合理、6 维齐全。
- `POST /profile/narrative` → 恰好两段：第 1 段背景优势（`tone=key, sourceId=m1`），
  第 2 段 Transformer 差距（`tone=weak`），sourceId 全部在材料白名单内。
- 错误映射实测：DeepSeek 连接失败时回包 `{"code":2001,"message":"LLM/Agent 生成失败：…","data":null,"traceId":…}`（HTTP 500）。

## 5. 边界确认 / 备注

- **知识库清理（已确认执行）**：删除早期测试灌入的 `doc_005(disign)`、`doc_006(前端开发总结)`
  （28 个切片同步移出向量库）——此前 nn 讲义最高分切片竟来自前端总结报告，污染 sources 与接地分母；
  清理后 sources 全部来自 seed_docs 三份教材。
- 真实模式首次调用 rag 节点 ~29s 为 reranker 模型首次加载 + BM25 索引重建，后续调用显著变快；
  同 kp+难度二次请求直接命中 `lecture@deepseek` 缓存（毫秒级）。
- `tests/test_b5b.py` 的真实链路用例自带缓存行前后清理（假 chunk 不遗留开发库）。
- mock 模式回归三重保障：pytest 逐字断言（三档 markdown / sources / rate）、
  conftest 强制 mock 基线、缓存 kind 按 provider 隔离。
- B6 接 Reinforce「Mock 与真实 Agent 双模式」时可直接复用本阶段 provider 分支模式与
  `LLMGenerationError → 2001` 映射；B8 指标脚本可复用 `grounding.sentence_grounding`。
