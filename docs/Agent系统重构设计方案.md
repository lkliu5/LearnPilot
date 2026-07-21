# Agent系统重构设计方案

> 任务：TASK-002-A Agent系统现状分析与重构方案设计  
> 文档性质：架构分析与设计，不包含代码变更  
> 设计基线：提交 `5bd4413`  
> 日期：2026-07-21

# 1 当前Agent系统分析

## 1.1 当前Agent调用流程

当前系统是“一条LangGraph资源生成主流程 + 多个独立Agent入口”，还不是统一Agent平台。

### LangGraph资源生成主流程

```text
POST /api/v1/workflow/execute
 → API校验用户、知识点、难度、岗位
 → workflow_runner启动后台线程、独立DB会话并绑定用户模型
 → diagnostic：读取画像/掌握度，调用Diagnostic Agent
 → retrieval：真实Retriever或确定性Mock检索
 → generation：读取画像、计算深度，调用Generator Agent
 → validation：调用Critic Agent或逐句Grounding
 → 通过则decision；未通过则最多重试2次；超限则降级
 → 持久化WorkflowTrace、回写讲义缓存
 → GET轮询或WebSocket推送快照
```

图拓扑：

```text
diagnostic → retrieval → generation → validation ──accept──→ decision → END
                                  ↑          │
                                  └──retry───┘
                                             └──fallback→ decision
```

### LangGraph之外的Agent入口

- 对话式画像Agent：由`services.profile_dialogue`维护会话和DB，Agent提供三阶段诊断规则。
- 知识路径规划Agent：由路径接口直接调用，读取画像、掌握度、岗位、知识树并确定性规划，可选LLM生成理由。
- 费曼评估Agent：由学习流程服务调用，历史会话和资源注入由服务层管理。
- 学习评估Agent：由Dashboard接口调用，服务聚合行为信号，Agent完成叙述和调整建议。

这些Agent共享`LLMClient`，但没有统一调度器、消息协议或共享任务上下文。

## 1.2 Agent目录结构

```text
backend/app/agents/
├── __init__.py              # Prompt读取、渲染、通用LLM入口
├── diagnostic_agent.py      # 资源生成前诊断
├── planner_agent.py         # 个性化路径规划
├── generator_agent.py       # RAG约束的讲义生成
├── critic_agent.py          # 内容审核与接地评价
├── dialogue_agent.py        # 三阶段画像诊断
├── feynman_agent.py         # 费曼讲解评估
└── evaluation_agent.py      # 学习过程评估

backend/app/workflows/
└── learning_workflow.py     # 三Agent资源生成图

backend/app/services/
└── workflow_runner.py       # 后台线程、快照、WS和运行态
```

现有Agent有三种形态：基于`run_agent()`的薄LLM角色、包含领域规则和DB查询的厚Agent、由服务管理上下文的LLM能力函数。抽象层级不统一。

## 1.3 LangGraph使用方式

当前使用`StateGraph(WorkflowState)`，每次运行动态构建并编译图。节点闭包捕获SQLAlchemy Session和Retriever；`stream_mode="values"`产生累积状态，`on_update`转换为轮询/WS快照；条件边完成审核重试和降级；最终轨迹写入`WorkflowTrace`。

当前未使用LangGraph checkpointer、interrupt、Command或子图。运行态、订阅队列和最近200次运行保存在单进程内存，持久化只覆盖最终轨迹。

## 1.4 当前能力边界

### 已具备

- 真实画像、掌握度和岗位驱动的诊断与内容深度适配。
- 真实RAG与零Key确定性Mock双通道。
- 生成、审核、重试、降级质量闭环。
- Prompt摘要、节点耗时、消息、证据和质量指标追踪。
- 轮询与WebSocket工作流可视化。
- 路径规划、对话诊断、费曼评估和过程评估等可复用能力。

### 尚不具备

- 没有统一任务规划Agent，图由开发者预先固定。
- Agent不能自主选择工具、委派任务或请求补充上下文。
- 不同Agent间没有版本化消息协议。
- 路径规划、教学交互和学习评估没有进入统一工作流。
- 运行中状态不能跨进程恢复。
- 质量反馈没有形成跨资源、画像和路径的长期闭环。
- 输入输出多为松散`dict[str, Any]`，缺少运行时契约。

# 2 当前问题分析

## 2.1 Agent角色划分

`dialogue_agent`与`diagnostic_agent`都属于诊断，但分别负责画像采集和生成前分析；`critic_agent`、`feynman_agent`和`evaluation_agent`都属于评价，但评价对象不同。缺少上位职责模型。

`planner_agent.py`同时承担DB读取、先修闭包、路径裁剪、排序、难度、时间线和资源装配，超出单一Agent边界。部分Agent是LLM角色，部分是确定性领域服务，命名口径不一致。

## 2.2 Agent自治能力

Agent只能执行调用方指定的步骤，不能拆解全局目标、维护能力清单、按结果选择工具、主动补充上下文或维护工作记忆。现有重试是固定条件边，不是自主反思。因此当前属于“受控工作流Agent”，不是真正自治系统。

## 2.3 Agent协作能力

当前`messages`主要服务前端展示，实际传递依赖共享State，无法正式表达任务委派、工具调用、证据引用、可重试失败、接管建议和结构化修订。图外Agent没有统一通道：费曼缺口不会自动触发规划，学习评估也不会自动形成重规划任务。

## 2.4 状态管理

`WorkflowState`仅适配讲义生成，业务数据、控制数据、展示数据和审计数据混合。缺少State版本、只读上下文与可变工作记忆的区分、字段运行时校验和持久化检查点。Session经闭包捕获，降低节点可测试性和可重放性。

## 2.5 任务规划

现有固定图是执行编排，`planner_agent`是知识点排序，都不是通用任务规划。系统不能从意图生成目标、拆分依赖子任务、匹配Agent/工具、动态改计划或统一控制预算、超时与终止条件。

## 2.6 质量反馈

当前最完整闭环是`Generator → Critic → Generator`，但仅针对单次讲义。阈值在多个模块重复；反馈多为字符串；不会统一影响教学交互和路径；人工复核缺少状态机；没有按Agent、模型、版本聚合长期质量；用户学习效果未反向评价资源质量。

# 3 目标多智能体架构设计

## 3.1 总体结构

采用“五类领域Agent + 受控编排器”。五类Agent代表职责层，可有多个实现；LangGraph负责协议校验、路由、权限、状态、预算和失败处理。

```text
用户目标/学习事件
 → 学习诊断Agent
 → 知识规划Agent
 → 资源生成Agent ←──────────┐
 → 教学交互Agent            │ 修订
 → 质量评估Agent ───────────┘
      ├→ 更新诊断证据
      ├→ 请求路径重规划
      └→ 结束或进入下一任务
```

## 3.2 学习诊断Agent

- 职责：汇总自述、微测、掌握度和行为；区分主观目标、客观能力、偏好；识别缺口、置信度和依据；判断信息是否充分。
- 输入：用户目标、StudentPortrait、Mastery、QuizAttempt、学习步骤、历史评价、知识范围。
- 输出：`DiagnosisResult`（能力基线、薄弱点、偏好、约束、置信度、证据）及必要的`ContextRequest`。
- 调用工具：画像查询、行为查询、诊断微测、画像抽取LLM。
- 关系：向规划Agent提供依据；请求交互Agent补充诊断；接收质量Agent回传的新学习证据。

## 3.3 知识规划Agent

- 职责：把目标拆为知识任务；依据先修、状态、岗位和预算生成计划；指定难度、资源、完成条件；支持不破坏已完成步骤的局部重规划。
- 输入：`DiagnosisResult`、知识图谱、岗位要求、时间预算、已有计划和评估反馈。
- 输出：`LearningPlan`、`TaskAssignment[]`和可解释规划依据。
- 调用工具：知识图谱、掌握度、岗位查询、先修闭包、KAP/CPDP算法、资源目录。
- 关系：消费诊断结果；向生成、交互、质量Agent下发子任务；接收质量Agent的重规划请求。

## 3.4 资源生成Agent

- 职责：生成讲义、图解、导图、练习、闪卡、分镜等；强制使用证据；按反馈局部修订；不修改画像和路径。
- 输入：`TaskAssignment`、学习者适配摘要、RAG证据包、上一轮反馈。
- 输出：`ResourceArtifact`和`GenerationReport`，失败时返回结构化错误。
- 调用工具：Hybrid Retrieval、Rerank、LLM网关、Mermaid、TTS、视频、资产存储。
- 关系：接收规划任务；产物先交质量Agent；通过后供交互Agent使用；接收修订请求。

## 3.5 教学交互Agent

- 职责：组织苏格拉底、费曼、康奈尔、选中即问和微测；选择教学策略；采集证据；发现卡点时请求资源或评价。
- 输入：当前计划步骤、已审核资源、对话历史、教学偏好、补充诊断任务。
- 输出：`TeachingTurn`、`LearningEvidence`、`ResourceRequest`或`EvaluationRequest`。
- 调用工具：会话存储、测验、费曼、康奈尔、资源检索和教学LLM。
- 关系：消费规划与合格资源；向质量Agent提交学习证据；协助诊断Agent补充信息。

## 3.6 质量评估Agent

- 职责：评价资源接地、内容安全、交互质量和学习效果；决定通过、修订、重规划或人工复核；聚合长期指标。
- 输入：`ResourceArtifact`、证据包、`TeachingTurn`、`LearningEvidence`、完成标准和历史质量。
- 输出：`QualityReport`、`RevisionRequest`、`ReplanRequest`、`DiagnosisUpdate`或`HumanReviewRequest`。
- 调用工具：Grounding、引用校验、内容安全、学习效果计算、规则评估器、独立评价模型。
- 关系：审核生成产物；评价教学效果；向诊断Agent回传证据；向规划Agent请求局部重规划。

# 4 Agent通信协议设计

## 4.1 Agent Message结构

执行协议与前端展示消息分离。建议统一消息：

```json
{
  "protocolVersion": "1.0",
  "messageId": "msg_xxx",
  "correlationId": "task_xxx",
  "causationId": "msg_parent_or_null",
  "workflowId": "wf_xxx",
  "sender": "diagnosis",
  "recipient": "planning",
  "messageType": "task.result",
  "timestamp": "ISO-8601",
  "payloadType": "DiagnosisResult",
  "payload": {},
  "evidenceRefs": ["evidence_xxx"],
  "metadata": {
    "attempt": 0,
    "priority": "normal",
    "provider": "mock",
    "model": "mock",
    "degraded": false
  },
  "error": null
}
```

最小消息类型：`task.request`、`task.accepted`、`task.result`、`task.failed`、`context.request`、`tool.request`、`tool.result`、`quality.feedback`、`plan.revision`、`human.review`。前端消息由投影器从执行事件生成。

## 4.2 状态传递方式

采用“共享State快照 + 不可变消息事件”双轨：

- State保存权威快照，节点只返回字段增量。
- Agent Message只追加，不修改历史。
- 大对象存入现有存储，State只保存artifactId/evidenceId。
- 节点输入输出均通过Schema校验。
- messageId/taskId支持幂等。
- 敏感画像按节点授权，展示投影不暴露Prompt、密钥和隐私。

## 4.3 任务上下文管理

任务上下文分四层：

1. `IdentityContext`：userId、角色、权限，仅读。
2. `LearningContext`：画像快照、掌握度、目标、偏好和知识范围，带版本。
3. `ExecutionContext`：计划、子任务、预算、重试、超时、取消。
4. `EvidenceContext`：检索证据、资源、评价和引用索引。

Agent不得直接管理Web请求或长期DB会话。数据库读取和状态提交通过服务/工具层完成，遵守TASK-001模块边界。

# 5 LangGraph工作流设计

## 5.1 State设计

```text
MultiAgentState
├── protocol_version
├── workflow_id / task_id / user_id
├── objective
├── learning_context
├── plan
├── messages
├── evidence_refs
├── artifacts
├── quality
├── control
├── errors
└── result
```

边界对象使用Pydantic等运行时Schema；LangGraph State可继续使用TypedDict，但不保存DB Session、Retriever实例或密钥。

## 5.2 Node设计

领域节点：

- `diagnose_learning`
- `plan_knowledge`
- `generate_resource`
- `teach_interactively`
- `evaluate_quality`

工具节点：

- `load_learning_context`
- `retrieve_evidence`
- `persist_artifact`
- `persist_learning_evidence`
- `project_runtime_snapshot`

控制节点：

- `classify_objective`
- `route_next_task`
- `apply_feedback`
- `request_human_review`
- `finalize_workflow`

节点必须单一职责、显式输入输出、无隐藏全局状态、可独立测试和幂等重放。

## 5.3 Edge设计

```text
START → load_context → classify_objective
  ├─ 新用户诊断 → diagnosis → planning
  ├─ 路径生成   → planning
  ├─ 资源生成   → planning/check → generation → quality
  ├─ 学习辅导   → interaction → quality
  └─ 学习评估   → quality

quality
  ├─ pass → persist/update → route_next_task
  ├─ revise_resource → generation
  ├─ continue_teaching → interaction
  ├─ update_diagnosis → diagnosis
  ├─ replan → planning
  └─ human_review → request_human_review

route_next_task
  ├─ has_next → 对应Agent节点
  └─ complete → finalize → END
```

复杂能力使用子图：诊断子图、资源生成子图、教学交互子图。条件边只能读取结构化枚举，不能解析自然语言路由。

## 5.4 异常处理机制

统一`WorkflowError`字段：

`errorId, category, code, node, agentId, toolName, message, retryable, attempt, maxAttempts, fallbackAction, occurredAt, traceId`。

处理策略：

- 输入/协议错误：立即失败，不重试。
- 临时工具错误：在预算内指数退避。
- LLM/外部服务错误：备用Provider或Mock降级。
- 质量不通过：进入结构化修订边，不视为技术异常。
- 状态冲突：重新加载上下文版本并局部重放。
- 超出预算：人工复核或可解释降级。
- 服务重启：从LangGraph持久化检查点恢复。

降级输出必须包含`degraded`、`fallbackReason`、`provider`、`model`、`requiresReview`。运行检查点用于恢复，WorkflowTrace用于审计和展示，两者分离。

# 6 后续实施计划

## TASK-002-B 代码重构阶段

建议顺序：

1. 建立`AgentMessage`、`TaskContext`、`WorkflowError`及五类Agent输出Schema。
2. 建立Agent能力接口与工具注册接口，禁止Agent持有Web请求或长期DB会话。
3. 把现有三Agent生成图迁移为资源生成子图，保持生成、审核、重试和降级行为不变。
4. 用适配器接入现有路径规划、教学交互和学习评估，暂不重写领域算法。
5. 建立顶层Router Graph，按任务类型调用子图。
6. 增加LangGraph检查点与任务上下文持久化接口；轻量环境先用SQLite。
7. 将内部事件投影为现有11.2快照，保持轮询和WebSocket契约。
8. 补充协议、节点、条件边、降级、恢复和兼容测试。

### TASK-002-B范围约束

- 不修改现有API路径、字段或枚举。
- 不重写RAG算法，RAG升级属于TASK-003。
- 不重写KAP/路径算法，算法升级属于TASK-004。
- 不替换生产任务队列，产品工程化属于TASK-005。
- 不删除既有Agent，采用适配、迁移、验证后再淘汰旧入口。
- 每次只迁移一个可验收子图。

### TASK-002-B验收建议

- 五类Agent均有可执行输入输出Schema。
- 资源生成子图保持现有契约快照通过。
- Agent消息可追踪、可关联、可校验，展示与执行协议分离。
- 结构化质量反馈可触发资源修订。
- Mock模式无Key可运行。
- 现有轮询、WebSocket和前端工作流无回归。

本文档完成后TASK-002-A停止；TASK-002-B须收到明确指令后另行说明修改方案并实施。

