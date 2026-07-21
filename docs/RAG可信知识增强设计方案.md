# RAG可信知识增强设计方案

> 任务：TASK-003-A RAG可信知识增强系统设计  
> 文档性质：架构分析与设计，不包含代码变更  
> 设计基线：`e05708b`  
> 日期：2026-07-21

# 1 当前RAG架构分析

## 1.1 总体数据流

当前系统已经形成“知识入库、混合检索、资源生成、接地校验”的基础链路，但不同业务入口对这些能力的组合方式不完全一致。

知识入库主链路：

```text
PDF / Markdown / TXT
  → 文本抽取
  → DocumentChunker 标题感知切片
  → Embedder 批量向量化
  → Chroma kb_chunks / 文档专属Collection
  → SQLite记录文档状态与切片数量
```

知识检索主链路：

```text
原始Query
  ├→ Dense：Embedder → Chroma cosine检索
  └→ Sparse：全量切片 → BM25
             ↓
          加权RRF融合
             ↓
      可选CrossEncoder重排
             ↓
          业务服务/Agent
```

生成和校验链路：

```text
检索切片 → Generator Agent Prompt
         → 生成Markdown
         → Critic / sentence_grounding
         → 通过、修订或降级
```

内置知识库使用固定集合`kb_chunks`；“文档学习”为每篇文档建立独立命名Collection，多文档生成时在内存中合并候选并统一重排。

## 1.2 Embedding流程

当前`Embedder`是进程内单例，采用延迟加载：

1. 首次调用时尝试加载`BAAI/bge-small-zh-v1.5`。
2. 模型成功加载时使用SentenceTransformer编码并进行L2归一化，模型维度为512。
3. 模型缺失、下载失败或加载异常时，自动切换为确定性哈希Embedding。
4. 哈希Embedding维度由`embedding_fallback_dim`配置，当前默认256。
5. 文档入库、查询向量化和逐句接地校验共享同一个Embedder入口。

该设计满足无网络、无模型仍可运行的Mock-first要求，但“同一逻辑集合可能先后被512维真实模型和256维降级模型访问”，是当前维度故障的直接结构性原因。

## 1.3 向量数据库

当前向量存储优先使用Chroma `PersistentClient`，目录为`./data/chroma`，距离空间为cosine，Embedding由应用显式提供。Chroma不可用时降级为JSON持久化的内存余弦库。

现有两类集合：

- `kb_chunks`：内置知识库共享集合。
- 文档专属集合：每篇学习文档一个命名空间，避免文档间和内置知识库互相污染。

当前Collection只声明了`hnsw:space=cosine`，没有保存Embedding模型、维度、归一化方式、语料版本和索引版本等元数据。Chroma会以首次写入向量的维度约束集合，后续不同维度的查询或写入会直接失败。

## 1.4 检索流程

`HybridRetriever`已经实现基础Hybrid RAG检索：

- Dense Retrieval：查询向量化后访问Chroma，候选池一般为`top_k × 2`。
- Keyword Retrieval：对Collection全量切片用`rank_bm25`建立BM25索引。
- Fusion：以Dense 0.7、Sparse 0.3、`rrf_k=60`进行加权RRF融合。
- Rerank：`Reranker`尝试加载`BAAI/bge-reranker-base` CrossEncoder；失败时按归一化RRF分数降级。

知识库检索测试、资源服务和文档生成服务显式调用了Reranker。但Retriever自身只负责召回和RRF，重排由调用方决定，因此新调用方可以无意绕过重排。

当前Query通常由知识点名称、难度或固定短语直接拼接，尚无独立的意图识别、查询改写、术语扩展、过滤条件生成或多查询召回阶段。

## 1.5 Agent调用方式

当前RAG不是Agent可发现、可声明调用的标准工具，而是由Workflow或Service预先注入上下文：

- 资源生成Agent：接收`rag_context`，将切片按`[1]、[2]`拼入Prompt，但输出没有结构化引用绑定。
- Critic Agent：接收生成文本与同一批`rag_context`，真实模式通过Embedding相似度计算逐句接地率。
- 旧学习工作流：Retrieval节点调用注入的Retriever，将结果写入`reranked_context`，再传给Generator和Critic。
- 新LearningGraph：资源节点消费`task_context.rag_context`；当前尚未内建独立RAG节点。
- 文档生成服务：执行文档专属Hybrid Retrieval、统一重排、生成以及逐句接地。
- 教学资源服务：执行混合检索和重排，并把来源映射到接口展示结构。

因此当前能力是“调用方编排RAG组件”，而不是“统一RAG服务向Agent返回版本化Evidence Package”。

## 1.6 当前能力边界

已经具备：

- 标题感知、带重叠窗口和来源位置的切片。
- 本地BGE Embedding与无模型哈希降级。
- Chroma持久化和文档集合隔离。
- Dense + BM25 + RRF混合召回。
- CrossEncoder重排组件及降级策略。
- 文档级来源元数据和部分页面/章节定位。
- 逐句接地检测、生成重试与降级闭环。

尚未形成：

- Embedding与Collection的强版本契约。
- 统一Query理解和检索策略选择。
- 强制重排、上下文过滤与Token预算控制。
- Claim到Citation的精确绑定和引用校验。
- 综合可信度评分、拒答策略与可解释证据包。
- 跨Agent统一的RAG输入输出协议和审计指标。

# 2 当前问题分析

## 2.1 Chroma维度不一致问题

当前真实模型输出512维，哈希降级默认输出256维。下列场景会产生`Collection expecting embedding with dimension of 512, got 256`或反向错误：

1. Collection由真实BGE向量首次创建，后续运行因模型加载失败改用256维哈希查询。
2. Collection由降级模式首次写入，后续模型成功加载后用512维访问。
3. 不同开发环境或进程使用不同Embedding配置访问同一个持久化目录。
4. 修改模型或fallback维度后复用旧Collection。

根因不是Chroma本身，而是系统没有把“模型、维度、预处理、归一化和语料版本”作为Collection Schema管理；运行时降级改变了向量空间，却仍访问同一集合。

此外，降级哈希向量与BGE向量不属于同一语义空间，即使人为补齐到相同维度也不能混用。维度相同只能保证接口形状兼容，不能保证向量语义兼容。

## 2.2 检索质量问题

- Query缺少意图分类、关键实体识别、知识点映射、同义词扩展和查询改写。
- 中文Sparse检索采用单字加英数词的轻量分词，对领域术语、短语和专有名词表达不足。
- 候选池大小、Dense/Sparse权重和RRF参数是全局静态配置，未按查询类型自适应。
- BM25仅按Collection数量变化失效；内容替换但总数不变时可能保留陈旧索引。
- 检索缺少文档状态、权限、课程、知识点、版本、时效性和质量等级等前置过滤。
- 没有离线检索评测集以及Recall@K、MRR、nDCG等持续指标。
- 多文档独立召回后直接合并，缺少跨Collection分数校准和每来源配额控制。

## 2.3 缺少统一重排序

项目已有`Reranker`实现，因此问题不是代码层完全缺失，而是架构层缺少强制性：

- `HybridRetriever.search()`返回RRF结果，Rerank由各调用方自行追加。
- 不同业务使用不同候选池和Top-K，结果不可比。
- Reranker降级只有`used`布尔值，缺少降级原因、模型版本、耗时和评分校准信息。
- 没有按查询类型选择重排策略，也没有对重复、冲突、过期内容做证据级重排。

目标架构应将Rerank设为可信RAG管道的标准阶段，只有显式策略允许时才能跳过，并在结果中记录实际执行路径。

## 2.4 缺少来源引用

现有切片保存`document_id`、标题和位置，部分接口也展示`sources`，但仍不是严格Citation机制：

- Generator Prompt中的`[1]`只是临时序号，生成结果未返回Claim与chunkId的结构化对应关系。
- 来源通常按文档去重，无法说明具体句子由哪个切片支持。
- 没有验证引用是否存在、是否支持对应Claim、是否发生错引或漏引。
- Workflow Trace保留检索上下文，但没有稳定的Citation ID和证据快照版本。
- 文档更新后，同一chunkId的内容一致性没有版本保证。

## 2.5 缺少可信度评价

现有`sentence_grounding`只衡量生成句子与检索文本的Embedding相似度，不能完整代表可信度：

- 相似不等于逻辑支持，尤其无法可靠判断数字、否定、因果、时间和比较关系。
- 无上下文时幻觉率返回0，容易被误读为“完全可信”。
- 未综合检索相关度、来源质量、来源一致性、引用覆盖率、事实支持率和模型降级状态。
- 评分阈值分散在配置和Agent常量中，校准与版本管理不足。
- 当前输出不能区分“可信”“证据不足”“来源冲突”“系统降级”和“必须人工复核”。

## 2.6 其他工程问题

- Embedder、Retriever、Reranker使用进程内单例，配置切换和模型升级缺少生命周期管理。
- Chroma与SQLite之间缺少原子一致性；元数据成功但向量失败时主要依赖状态字段补偿。
- Collection命名没有编码Embedding版本，不利于蓝绿迁移。
- 缺少端到端trace：无法统一关联Query改写、召回、重排、过滤、生成、引用和质量判断。
- 可信策略没有集中配置，业务服务容易产生不同口径。

# 3 目标RAG架构设计

## 3.1 设计原则

1. 可信优先：无证据时明确返回证据不足，不把降级结果表述为高可信答案。
2. 协议优先：Agent只消费结构化Evidence Package，不直接依赖Chroma结果字典。
3. 空间隔离：不同Embedding空间永不混写、混查。
4. 可降级但可感知：模型失败可回落，结果必须携带降级状态和风险。
5. 可审计：每个结论可追溯到固定版本的切片和原始文档位置。
6. 渐进迁移：新管道与旧Retriever并行，不直接替换已验收接口。

## 3.2 Hybrid RAG总体流程

```text
Query理解
  ↓
QueryPlan（意图、改写、过滤条件、检索策略）
  ↓
  ├──────── Dense Retrieval ────────┐
  └──────── Keyword Retrieval ──────┤
                                     ↓
                              Fusion + Rerank
                                     ↓
                              Context Filtering
                                     ↓
                              Evidence Package
                                     ↓
                                 Generation
                                     ↓
                                  Citation
                                     ↓
                             Quality Evaluation
                         ┌───────────┼───────────┐
                       PASS        REVISE      FALLBACK
```

## 3.3 Query理解

Query Understanding输出`QueryPlan`，不直接生成答案：

```text
QueryPlan
- original_query
- normalized_query
- intent: explain | compare | procedure | diagnose | generate | verify
- knowledge_points[]
- entities[]
- expanded_queries[]
- filters: course/document/category/version/permission
- retrieval_policy
- freshness_requirement
- language
```

优先使用确定性规则完成知识点ID映射、过滤条件和基础规范化；LLM仅负责歧义消解、查询改写和术语扩展。LLM不可用时仍使用原Query执行后续流程。

## 3.4 Dense Retrieval与Keyword Retrieval

Dense Retrieval：

- 只访问与`EmbeddingProfile`完全匹配的Collection。
- 支持元数据过滤和候选数量配置。
- 返回原始距离、标准化分数、模型版本和Collection版本。

Keyword Retrieval：

- TASK-003阶段继续采用轻量BM25，避免引入外部搜索基础设施。
- 改为版本化索引，使用内容指纹而非仅Collection计数判断失效。
- 加入领域词典、知识点名称、别名和英文术语的短语Token。
- 返回BM25原始分、排名和命中词。

两路召回通过RRF融合。权重由`retrieval_policy`选择，例如定义型问题偏Dense，精确术语、编号和代码符号查询提高Keyword权重。

## 3.5 Rerank

统一由`TrustedRAGPipeline`调用Reranker，调用方不再自行拼装：

- 输入：规范化Query、候选切片、候选来源和策略。
- 输出：重排分、排名、模型版本、是否降级、降级原因和耗时。
- 默认候选池20，输出5至8条；具体值通过评测标定。
- CrossEncoder不可用时降级为RRF，但`degraded=true`，可信度上限同步降低。
- 去除高度重复切片，限制单文档垄断候选，保留来源多样性。

## 3.6 Context Filtering

重排后增加独立上下文过滤阶段：

- 相关性阈值：过滤低分候选。
- 权限与状态：只允许已索引、可访问、未归档的文档。
- 时效性：需要最新知识时优先有效版本。
- 冲突检测：识别同一事实的互斥表述并标记`conflict`。
- 去重与覆盖：保留不同子主题和不同可信来源。
- Token预算：按Query子目标分配上下文预算，避免简单截断破坏证据。

过滤结果形成不可变`EvidencePackage`：

```text
EvidencePackage
- request_id / trace_id
- query_plan
- retrieval_profile
- evidence_items[]
- coverage
- conflicts[]
- degraded
- warnings[]
```

每个`EvidenceItem`至少包含：

```text
- evidence_id
- chunk_id
- document_id
- document_version
- title
- source_location
- content
- content_hash
- dense_score
- keyword_score
- fusion_score
- rerank_score
- source_quality
```

## 3.7 Generation

Generation只接收`EvidencePackage`中的允许字段：

- Prompt明确要求事实性Claim附带`[evidence_id]`。
- 证据覆盖不足时允许解释边界或拒答，不允许用模型常识补齐为确定事实。
- 输出分为正文、Claims和引用列表，避免后处理仅靠正则猜测引用。
- 记录实际使用的Evidence ID，不把全部召回结果伪装为已引用来源。

## 3.8 Citation

Citation阶段负责生成与验证引用，不只是展示来源列表：

```text
Citation
- citation_id
- claim_id
- evidence_id
- document_id
- document_version
- source_location
- support_score
- status: supported | partial | unsupported | missing
```

校验规则：

1. 引用的Evidence必须属于本次Evidence Package。
2. Evidence内容哈希必须与检索快照一致。
3. 每个事实性Claim至少有一个有效引用。
4. 引用支持度不足时标记为`partial/unsupported`并进入修订。
5. 展示层可按Citation回溯到文档标题、页码或章节。

## 3.9 Quality Evaluation

可信度不采用单一相似度，而采用多维评分：

```text
trust_score =
  0.25 × retrieval_relevance
  + 0.20 × source_quality
  + 0.25 × claim_support
  + 0.15 × citation_coverage
  + 0.15 × source_consistency
  - degradation_penalty
```

初始权重仅作为实现基线，必须通过TASK-003后续评测集校准。输出：

```text
TrustReport
- decision: PASS | REVISE | FALLBACK | HUMAN_REVIEW
- trust_score
- retrieval_relevance
- source_quality
- claim_support
- citation_coverage
- source_consistency
- hallucination_rate
- degraded
- issues[]
- revision_instructions[]
```

推荐路由：

- PASS：证据充足、引用完整且无关键冲突。
- REVISE：证据足够但答案存在漏引、错引或未接地Claim。
- FALLBACK：检索为空、核心证据不足或关键模型降级导致无法安全生成。
- HUMAN_REVIEW：权威来源冲突、高风险教学结论或多次修订失败。

# 4 Embedding统一方案

## 4.1 模型选择

主模型继续使用`BAAI/bge-small-zh-v1.5`，理由是中文能力、512维规模和当前代码兼容性较好，满足轻量部署要求。TASK-003阶段不引入远程Embedding依赖。

降级方案调整为：

- 哈希Embedding只写入独立的fallback Collection，不访问BGE Collection。
- 真实模型不可用时，优先启用Keyword-only检索；如确需Dense降级，则使用独立哈希空间。
- Grounding必须使用与Evidence相同的Embedding Profile，或明确改用词面规则降级。

## 4.2 EmbeddingProfile

新增逻辑上的版本化配置对象：

```text
EmbeddingProfile
- profile_id: bge-small-zh-v1.5@1
- provider: sentence-transformers
- model_name: BAAI/bge-small-zh-v1.5
- dimension: 512
- normalize: true
- distance: cosine
- preprocessing_version: text-v1
- fallback_profile_id: hash-token@1
```

启动后首次使用模型时校验实际维度，禁止只相信配置值。所有写入和查询必须携带`profile_id`。

## 4.3 维度管理

Collection命名建议：

```text
kb_chunks__bge_small_zh_v1_5__d512__v1
kb_chunks__hash_token__d256__v1
doc_<id>__bge_small_zh_v1_5__d512__v1
```

Collection元数据至少保存：

- `embedding_profile_id`
- `embedding_model`
- `embedding_dimension`
- `normalize`
- `distance`
- `preprocessing_version`
- `schema_version`
- `created_at`

访问Collection前执行三项校验：Profile一致、实际Query维度一致、Collection Schema版本兼容。任一不一致时停止Dense访问并返回可识别错误，由管道选择Keyword-only或迁移后的新Collection，不能继续尝试混用。

## 4.4 Collection迁移方案

采用“新建、回填、验证、切换、保留回滚”的蓝绿迁移，禁止原地修改既有Collection：

1. Inventory：枚举现有Collection、记录数量、实际维度、文档版本和异常状态。
2. Freeze Profile：确定目标Profile为BGE 512维v1。
3. Create：创建带完整元数据的新Collection。
4. Re-embed：从原始文档重新抽取和切片；不得把旧向量填充或截断到新维度。
5. Dual Validation：验证记录数、随机内容哈希、维度、Top-K检索结果和来源完整性。
6. Shadow Read：线上主链路仍读旧集合，新管道旁路读取新集合并记录差异。
7. Atomic Switch：通过Collection Alias或配置映射切换读路径。
8. Observation：保留旧集合一段观察期，监测错误率与检索指标。
9. Cleanup：确认回滚窗口结束后再由独立任务清理旧集合。

迁移期间若主模型不可用，不应把哈希向量写进目标BGE Collection；任务应暂停或写入独立fallback Collection。

## 4.5 写入一致性

推荐索引任务状态：

```text
pending → extracting → chunking → embedding → indexing → validating → indexed
                                                        └→ failed
```

SQLite保存文档版本、内容哈希、Embedding Profile、Collection和索引状态。只有Chroma写入及验证完成后才标记`indexed`。失败时保留错误阶段和可重试信息。

# 5 Agent与RAG融合设计

## 5.1 调用RAG的Agent

### 学习诊断Agent

可选调用。用于获取知识点能力标准、先修关系和诊断题依据，不用于检索用户隐私信息。

### 知识规划Agent

必须调用。检索知识图谱说明、课程结构、岗位能力标准和资源目录，为任务拆解提供依据。

### 资源生成Agent

必须调用。消费通过过滤的Evidence Package生成讲义、练习、图解等，并输出结构化Citation。

### 教学交互Agent

按需调用。针对学生追问进行会话Query改写和小范围检索；必须结合当前教学上下文，防止检索漂移。

### 质量评估Agent

必须消费RAG产物，但原则上不重新使用完全不同的隐式证据。它校验Claims、Citations、Evidence Package和生成结果；需要补证时发出明确的`EvidenceRequest`。

## 5.2 RAG工具输入协议

```text
RAGRequest
- request_id
- task_id
- trace_id
- agent_name
- query
- intent
- knowledge_points[]
- filters
- top_k
- token_budget
- retrieval_policy
- required_source_quality
- conversation_context摘要
```

约束：Agent不能直接传入任意Chroma集合名；集合选择由权限与知识域映射完成。`trace_id`沿用AgentMessage元数据，贯穿整个RAG管道。

## 5.3 RAG工具输出协议

```text
RAGResponse
- request_id
- trace_id
- query_plan
- evidence_package
- retrieval_metrics
- degraded
- warnings[]
- error
```

`retrieval_metrics`至少包括Dense/Sparse候选数、重排是否使用、过滤数量、耗时、Embedding Profile和Collection版本。

## 5.4 Agent状态融合

AgentState建议扩展逻辑字段：

```text
- evidence_packages: 按任务和Query保存的证据包引用
- active_evidence_id
- citations
- trust_report
- rag_execution_history
```

完整大文本不宜在每个LangGraph节点反复复制；State保存证据包ID和必要摘要，正文由RAG Repository按ID读取。Execution History只记录协议摘要、版本、指标和决策。

## 5.5 工作流关系

建议在新LearningGraph中以独立节点并行演进：

```text
Diagnosis
  → RAGQueryPlan
  → TrustedRetrieval
  → ResourceGeneration
  → CitationValidation
  → QualityCritic
```

质量路由保持TASK-002-B4的`PASS/REVISE/FALLBACK`语义：

- 引用或表述问题：REVISE回ResourceGeneration。
- 证据不足：重新进入TrustedRetrieval，但必须限制检索重试次数。
- 模型/索引不可用或重试耗尽：FALLBACK。

# 6 TASK-003-B以后实施计划

## TASK-003-B1：Embedding契约与维度治理

目标：先消除当前最直接的运行故障。

- 实现EmbeddingProfile与运行时维度校验。
- 按Profile隔离Collection。
- 增加维度不匹配的显式错误与Keyword-only降级。
- 增加旧Collection盘点和迁移工具的dry-run能力。
- 测试真实512维、哈希256维、跨Profile拒绝访问和降级路径。

验收重点：任何环境切换均不能再向不兼容Collection发起查询或写入。

## TASK-003-B2：统一Trusted Retrieval Pipeline

- 建立QueryPlan、RAGRequest、RAGResponse和EvidenceItem Schema。
- 将Dense、Keyword、RRF、Rerank封装为强制统一管道。
- 增加元数据过滤、去重、来源配额和Token预算过滤。
- 保留旧Retriever入口，以Adapter方式并行接入。

验收重点：新调用方无法无意绕过重排和过滤，旧API行为不变。

## TASK-003-B3：Citation机制

- 为文档版本、切片内容哈希和Evidence ID建立稳定标识。
- 资源生成输出Claims与Citation映射。
- 增加漏引、错引、失效引用和引用覆盖率校验。
- 前端接口变更如有需要，先单独设计兼容映射，不在本阶段直接修改。

验收重点：任一事实性Claim能够定位到具体文档版本和页码/章节。

## TASK-003-B4：可信度评价与Agent闭环

- 实现TrustReport多维评分。
- 将Citation Validator和RAG质量信息接入Quality Evaluation Agent。
- 支持PASS、REVISE、FALLBACK、HUMAN_REVIEW路由。
- 与TASK-002的新LearningGraph并行集成，不替换旧工作流。

验收重点：检索为空、来源冲突、重排降级和引用不足均有确定且可审计的路由结果。

## TASK-003-B5：Collection迁移与灰度切换

- 执行蓝绿重建、影子检索和差异报告。
- 校验数据完整性、来源完整性及检索质量。
- 配置化切换新Collection，并保留回滚窗口。

验收重点：迁移不原地破坏旧集合，切换失败可回滚。

## TASK-003-C：评测与可观测性

- 建立领域查询、精确术语、跨文档综合、证据不足和冲突来源评测集。
- 指标包括Recall@K、MRR、nDCG、Citation Precision/Recall、Claim Support Rate、Fallback Rate和P95耗时。
- 记录各阶段trace、模型/Profile版本、候选数量、降级原因和可信度分解。
- 以评测结果校准RRF权重、Top-K、过滤阈值和Trust Score权重。

## 实施顺序与边界

严格顺序建议为：

```text
B1 维度治理
 → B2 统一检索管道
 → B3 Citation
 → B4 Agent可信闭环
 → B5 Collection迁移
 → C 评测与持续优化
```

每个阶段均采用新旧并行、Adapter兼容和可回滚策略。TASK-003-A仅交付本设计文档，不修改任何后端或前端代码。
