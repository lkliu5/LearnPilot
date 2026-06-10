"""RAG 管道（B3）。

chunker（标题感知 + 重叠切片）→ embeddings（bge-small-zh，延迟加载/降级）
→ vector_store（Chroma 持久化）→ retriever（BM25 + 向量 RRF 融合）
→ reranker（bge-reranker，失败降级仅 RRF）。

所有重型本地模型（sentence-transformers / chromadb）均**延迟加载**且**加载失败自动降级**，
保证无网络、无模型文件时仍能跑通全链路（对齐 CLAUDE.md「无密钥可跑通」纪律）。
"""
