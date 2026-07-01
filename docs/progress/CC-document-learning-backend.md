# CC 文档学习 · 会话一（后端主链路）完成总结

> 平行独立链路：上传文档 → 解析入**专属向量集合**（隔离内置库）→ 基于文档复用现有引擎生成
> 讲义/视频/图解/思维导图/练习题/闪卡 → 进「我的资源库」（带文档来源标识）。
> **未改动**内置课程画像/诊断/路径/掌握度/既有生成接口签名。

## 一、改动文件清单

### 新增（5 个）
| 文件 | 职责 |
| --- | --- |
| `app/services/document_parse.py` | PDF(pypdf)/txt/md/Word(python-docx) 文本抽取，段落+页码定位 |
| `app/services/document_store.py` | 用户文档 CRUD + 异步入库到**专属向量集合**（隔离内置 kb_chunks） |
| `app/services/document_generation.py` | 6 类生成编排（复用检索/生成 Agent/接地/内容安全），带资源库埋点 |
| `app/schemas/document.py` | 文档学习请求体（JSON） |
| `app/api/v1/document.py` | 文档学习路由（上传/列表/详情/删除 + 6 个生成接口） |

### 编辑（均为**加法**，不改既有签名/行为）
| 文件 | 改动 |
| --- | --- |
| `app/models/entities.py` | 新增 `Document` 表；`GenerationLog` 加 `source/doc_id/doc_title` 三列（可空） |
| `app/core/init_db.py` | 注册 `Document`；`_migrate_genlog_source()` 补列（幂等） |
| `app/rag/vector_store.py` | `_ChromaStore/_NumpyStore` 加 `collection` 参数；新增 `get_collection_store()`/`drop_collection()`（内置 `get_vector_store()` 单例不变） |
| `app/rag/retriever.py` | `HybridRetriever` 加可注入 `store_getter`（默认内置库）；新增 `get_document_retriever(collection)` |
| `app/core/llm.py` | 新增 `generate_flashcards`/`generate_doc_quiz`（mock/real 双模）+ `_doc_key_sentences`；纳入内容安全 guard 列表 |
| `app/services/generation_log.py` | 新增 `record_document()`；`list_history` 加 `source` 过滤 + `source/docId/docTitle` 字段（内置行行为不变） |
| `app/main.py` | 挂载 `document.router` |
| `docs/后端接口文档.md` | 新增第 20 章 + 19.1 增补字段 |
| `tests/test_document_learning.py` | 新增 9 用例（全链路 + 隔离 + 回归 + 鉴权） |

## 二、隔离设计（红线核心）

- **向量集合隔离**：每篇文档一个专属 collection `doclearn_<docId>`；内置课程用 `kb_chunks`。
  Chroma 物理分集合；降级 numpy 库按集合独立 JSON 文件。互不检索、互不污染。
- **检索隔离**：`get_document_retriever(collection)` 用注入式 store，内置 `get_retriever()` 单例不动。
- **数据隔离**：`Document` 表 `user_id` 隔离键（无外键）；生成不读画像/掌握度、不写 KnowledgePoint。
- **复用不重造**：检索(RRF+rerank)、生成 Agent、逐句接地防幻觉、内容安全 guard、TTS 全部复用。

## 三、启动命令

```bash
cd backend && uvicorn app.main:app --reload --port 8000   # 表结构启动时自动迁移建立
cd backend && pytest -q
```

## 四、验证命令与实测结果

### 1. 全量测试（回归 + 新增，mock 基线）
```
cd backend && python -m pytest -q
→ 238 passed, 1 skipped, 1 warning in 144.67s     # 0 失败，内置主线无回归
cd backend && python -m pytest tests/test_document_learning.py -q
→ 9 passed in 75.79s
```
覆盖：上传 PDF+md → 解析分块入专属集合（indexed, chunks>0）；集合与内置 kb_chunks 隔离
（文档独有 token 不进内置检索）；讲义/图解/思维导图/练习题/闪卡内容含文档独有 token；
讲义带逐句接地 hallucinationRate、sources 标 `文档`；练习题答案自洽；产物进资源库
`source=document`；内置资源库仍 `source=builtin`、kpName 回填正常；归属/鉴权（1002/1004）。

### 2. 真实 provider（DeepSeek）实测（.env 有真实 Key，服务端 8010）
上传 `kappa.md`（含独有词 `KappaAttn`）→ 入库 `succeeded`，`status=indexed chunks=2`：
```
=== LECTURE (real deepseek) ===
hallucinationRate= 0.1786 | sources= [
  {"title":"kappa · 卡帕注意力机制 / 段落 1","type":"文档","confidence":0.7},
  {"title":"kappa · 卡帕注意力机制 / 复杂度 / 段落 1","type":"文档","confidence":0.51}]
markdown has KappaAttn: True
=== FLASHCARDS (real) === {"front":"卡帕注意力如何提升长序列建模能力？",
                          "back":"通过对查询向量施加 kappa 缩放，强化关键 token 权重分配。"}
=== QUIZ (real) === single | 卡帕注意力（KappaAttn）通过什么方式强化关键 token 权重分配？
=== RESOURCE LIB (document) === [('quiz','kappa'),('flashcard','kappa'),('lecture','kappa')]
```
证明：真实模式下生成内容确实取自上传文档、防幻觉对文档生效、进资源库带来源标识。

## 五、红线自检

- [x] 未改内置画像/诊断/学习路径/掌握度/既有生成接口签名（仅**新增**接口与**加法**字段）。
- [x] 向量集合与内置库物理隔离（Chroma collection / 降级 JSON 命名空间）。
- [x] 复用现有 RAG / 生成 Agent / Critic 接地 / 内容安全 / TTS，未重造。
- [x] 统一信封；异步任务 taskId 轮询；Mock 无 Key 可跑通全链路。
- [x] PDF 用 pypdf、Word 用 python-docx（成熟库）；大文档按现有 chunker 分块。
- [x] 全量 238 passed 0 failed，内置主线无回归。

## 六、已知边界（留待后续，本轮范围外）

- 基于文档的**学习路径**未做（CC 明确第二步）。
- 图片 OCR / 网页来源未做（范围外）。
- 文档生成暂不走 ResourceCache 缓存（用户私有、低频，每次实时生成）；如需可后续按
  `(doc_id,kind,difficulty)` 加缓存（不影响契约）。
- 前端页面为**会话二**（NotebookLM 式布局），本会话仅后端主链路。
