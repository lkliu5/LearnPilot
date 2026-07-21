# Embedding规范说明

> 任务：TASK-003-B1 Embedding统一与知识库环境治理  
> 基线：`1d37c3d`

## 1 调用链

```text
知识入库：文档抽取 → Chunker → Embedder.embed_texts → VectorStore.add → Chroma
知识查询：Query → Embedder.embed_query → VectorStore.query → HybridRetriever
质量校验：生成句/证据片段 → Embedder.embed_texts → cosine接地判断
文档学习：文档专属Collection复用同一Embedder与VectorStore契约
```

所有Embedding调用统一经过`app.rag.embeddings.Embedder`。业务服务不得自行指定向量维度，也不得直接构造与当前Profile不一致的向量。

## 2 统一配置

Embedding空间由以下配置集中定义：

- `embedding_provider`：默认`sentence-transformers`。
- `embedding_model_name`：默认`BAAI/bge-small-zh-v1.5`。
- `embedding_dimension`：默认512。

三项组成不可分割的`EmbeddingProfile`。`profile_id`用于日志、Collection元数据和迁移审计。旧`embedding_fallback_dim`仅为环境配置兼容保留，新代码不得使用它决定向量形状。

## 3 降级规则

主模型加载失败时允许使用确定性哈希Embedding，但输出维度仍必须等于`embedding_dimension`。这保证接口和Collection维度稳定。

哈希向量与BGE向量语义空间不同，因此降级状态必须记录日志；后续TASK-003-B2应进一步采用独立空间或Keyword-only策略。当前阶段重点是杜绝256/512维向量混用和不可解释的Chroma底层异常。

## 4 维度校验

执行三层校验：

1. 模型加载：模型报告的实际维度必须等于Profile维度。
2. Collection打开：Collection声明维度或已有样本维度必须匹配Profile。
3. 写入与查询：每个Add向量和Query向量必须匹配Profile。

错误统一抛出`EmbeddingDimensionError`，消息包含上下文、期望维度和实际维度。禁止通过截断、补零或静默重建规避错误。

## 5 Collection元数据

新Collection写入：

- `embedding_provider`
- `embedding_model`
- `embedding_dimension`
- `embedding_profile_id`
- `hnsw:space=cosine`

旧Collection没有这些字段时，通过已有向量样本推断实际维度。空旧Collection允许按当前Profile使用；非空且维度不一致时明确报错并要求迁移。

## 6 迁移规范

脚本：`backend/scripts/migrate_embedding_collection.py`

默认dry-run：

```bash
cd backend
python scripts/migrate_embedding_collection.py kb_chunks kb_chunks_bge_d512_v1
```

实际执行：

```bash
python scripts/migrate_embedding_collection.py kb_chunks kb_chunks_bge_d512_v1 --execute
```

迁移行为：读取旧Collection的文档与元数据，使用当前EmbeddingProfile重新编码，写入新Collection。脚本不删除源Collection，不允许源目标同名，也不覆盖非空目标Collection。

## 7 运维要求

- 修改模型或维度必须创建新Collection并执行重新Embedding。
- 禁止在原Collection中混写不同模型或不同预处理版本的向量。
- 环境部署前先执行dry-run并核对源记录数、目标名称、Profile和维度。
- 迁移完成后应验证记录数、随机内容、查询结果与来源元数据，再由后续任务完成灰度切换。
