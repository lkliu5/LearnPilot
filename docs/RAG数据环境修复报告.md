# RAG数据环境修复报告

> 任务：TASK-003-C2 RAG数据环境修复与稳态检索基线重建  
> 前置基线：`a238874`  
> 执行日期：2026-07-21

# 1 乱码根因

## 1.1 完整链路检查

检查范围：

```text
seed_docs源文件
 → UTF-8读取
 → DocumentChunker
 → Chroma写入/读取
 → EvidenceItem构建
```

35篇`backend/seed_docs/**/*.md`（含`network/`下5篇）全部通过UTF-8 strict解码：

- 替换字符`�`：0
- 异常控制字符：0
- 高比例不可打印字符：0
- 已知错误解码特征：0
- 非UTF-8文件：0

对旧`kb_chunks`的147个切片直接通过Python/Chroma API审计，乱码检测结果同样为0。此前终端中出现`ÊÇ`、`µÄ`、`£¬`等显示，不是Chroma正文实际损坏，而是PowerShell/工具输出链路的字符集解释不一致。将Python输出写入UTF-8 JSON后再读取，中文内容保持正常。

因此，“中文乱码”的根因是诊断展示链路编码不一致，而非源文档、切片器或Chroma存储将UTF-8正文错误解码。原C1报告将终端显示现象描述为“历史Chroma乱码”，本报告对此进行纠正。

## 1.2 实际数据问题

旧Collection仍存在真实的数据完整性问题：

- 旧Collection：29篇文档、147个切片。
- `doc_001`及5篇`network/`文档缺失。
- 源目录：35篇文档。
- 旧Collection没有本阶段要求的完整编码、切片版本和创建时间元数据。

## 1.3 修复措施

新增统一文本质量模块，提供：

- UTF-8 BOM兼容但严格解码，禁止`errors="ignore"`。
- 非UTF-8文件抛出包含文件和错误字节位置的`TextEncodingError`。
- 检测`�`、异常控制字符、不可打印字符比例和常见mojibake特征。
- Collection写入前逐条校验正文。
- Evidence构建时再次校验，发现乱码直接报错，不隐藏或清洗掉问题。
- 空文本和重复Chunk检查。

乱码文档与切片清单：

```text
源文档：[]
旧kb_chunks异常切片：[]
新Collection异常切片：[]
```

# 2 模型加载根因

## 2.1 诊断结果

当前模型配置：

```text
model: BAAI/bge-small-zh-v1.5
dimension: 512
```

独立执行`import torch`即可复现失败，无需进入SentenceTransformer或模型下载阶段：

```text
PermissionError: [WinError 5] 拒绝访问
Error loading torch/lib/torch_python.dll or one of its dependencies
```

只读检查结果：

- `torch_python.dll`存在，约19.5MB。
- 当前沙箱用户对文件具有Modify/Synchronize ACL。
- Python可以完整读取DLL字节。
- DLL没有额外Mark-of-the-Web数据流。
- Windows动态加载器仍在加载该DLL或依赖DLL时返回Access Denied。

因此可排除“文件不存在”和“普通文件读取权限不足”。在不进行系统级权限修改的前提下，当前证据只能定位为：托管运行时中的Torch DLL加载/执行策略或其依赖DLL加载受限。不能仅凭错误信息断言具体是哪一个依赖DLL或安全策略。

## 2.2 运行模式治理

Embedding现在明确区分：

- `real_embedding`
- `hash_fallback`
- `unavailable`

新增配置：

- `embedding_allow_fallback`：业务运行是否允许哈希降级。
- `embedding_evaluation_require_real`：评测是否必须使用真实模型。

应用启动会记录模式、provider、模型、维度、是否允许fallback及是否加载失败，不记录完整正文或用户信息。评测脚本输出完整Embedding Runtime对象。

当使用`--require-real`时，加载失败立即退出并生成blocked结果，退出码为2。本次真实BGE评测未产生任何伪指标。

## 2.3 可复现修复步骤

建议在非托管沙箱的独立64位Python虚拟环境中验证，不修改系统目录ACL：

1. 安装与Python版本匹配的Microsoft Visual C++ 2015–2022 x64 Runtime。
2. 新建干净虚拟环境，避免复用当前托管runtime依赖目录。
3. 从PyTorch官方CPU wheel源安装与Python版本匹配的`torch`。
4. 安装项目锁定版本的`sentence-transformers`。
5. 先执行`python -c "import torch; print(torch.__version__)"`。
6. 再执行SentenceTransformer离线加载测试。
7. 配置项目`MODEL_CACHE_DIR`到可读写的模型缓存目录。
8. 运行`evaluate_retrieval.py --embedding-mode real --require-real`。

在第5步通过前，不应下载或重建真实BGE Collection，因为问题发生在模型加载之前。

# 3 修复内容

- 新增UTF-8严格读取和文本质量门禁。
- Collection写入和Evidence构建显式拒绝乱码。
- 新增Embedding模式、失败原因和fallback策略。
- 强制真实评测失败时阻断，不再静默降级。
- 新增蓝绿Collection重建脚本和完整质量验证。
- 评测脚本支持明确选择Collection和Embedding模式。
- 增加应用启动Embedding模式日志。
- 扩展评测集并增加标注治理字段与失效ID检查。

# 4 Collection重建信息

执行前dry-run：

```text
target: kb_chunks__hash_d512__utf8_v2
mode: hash_fallback
profile: hash:deterministic_hash_v1:d512
documents: 35
chunks: 178
bad documents: 0
empty chunks: 0
duplicate groups: 0
```

新Collection：

```text
name: kb_chunks__hash_d512__utf8_v2
documents: 35
chunks: 178
dimension: 512
created_at: 2026-07-21T08:57:07.074084+00:00
```

元数据：

```text
embedding_profile_id: hash:deterministic_hash_v1:d512
embedding_provider: hash
embedding_model: deterministic-hash-v1
embedding_dimension: 512
source_encoding: utf-8
chunking_version: heading-window-v1
created_at: 2026-07-21T08:57:07.074084+00:00
```

旧`kb_chunks`和新Collection均可独立打开。生产默认仍为`kb_chunks`，本阶段没有切换。

# 5 数据质量检查结果

| 检查项 | 旧Collection | 新Collection |
|---|---:|---:|
| 文档数 | 29 | 35 |
| Chunk数 | 147 | 178 |
| Embedding维度 | 512 | 512 |
| 乱码Chunk | 0 | 0 |
| 空Chunk | 0 | 0 |
| 重复Chunk组 | 0 | 0 |
| 完整Profile元数据 | 否 | 是 |

# 6 未解决问题

- 当前托管运行时仍不能加载Torch DLL，真实BGE基线blocked。
- 40条评测用例均只有第一标注者，第二人复核状态为pending。
- 应用业务入口仍读取旧Collection，符合本阶段“不切换生产”的限制。
- 文本质量规则属于工程门禁，仍可能存在未覆盖的罕见错误解码模式。

# 7 回滚方式

本次无需业务回滚：生产默认Collection从未切换，旧`kb_chunks`未修改、未删除。

若后续不采用新Collection，只需继续保持默认配置不变。新Collection的删除属于独立破坏性运维动作，必须在确认不再需要评测复现且获得明确授权后执行；本阶段不删除。
