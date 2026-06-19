"""应用配置（pydantic-settings）。

读取 backend/.env（可选），所有字段均带默认值——无 .env、无密钥也能启动。
后续阶段（B1+）在此追加数据库 / LLM 等配置项。
"""
from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # 允许 model_cache_dir / model_xxx 等字段名（默认 model_ 为 pydantic 保护命名空间）
        protected_namespaces=(),
    )

    # 应用元信息
    app_name: str = "智学中枢后端"
    api_prefix: str = "/api/v1"

    # CORS 允许来源（默认放行前端 Vite 3000/3001）
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # LLM Provider（mock / deepseek / qwen / anthropic）
    llm_provider: str = "mock"

    # DeepSeek（B5-b 真实生成，OpenAI 兼容协议）：Key 经 backend/.env 注入，
    # 缺省为空——mock 模式无任何 Key 必须能跑通全链路（CLAUDE.md 纪律）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 60.0
    llm_temperature: float = 0.3

    # 内容安全过滤（app/core/content_safety.py）：所有 LLM 生成文本返回前统一过滤。
    # - enabled：总开关（默认开）；
    # - model_check：可选的模型级二次校验（真实 provider 下用 LLMClient 通道做轻量
    #   违规分类补漏，失败回落词表；mock / 无 Key 自动不生效，默认关，避免拖慢链路）；
    # - lexicon_path：可选扩充词库（每行 `类别:词`，类别取 political|porn|
    #   violence_terror|illegal_harmful|abuse_discrimination），缺省仅用内置种子词表。
    content_safety_enabled: bool = True
    content_safety_model_check: bool = False
    content_safety_lexicon_path: str = ""

    # 15.3 逐句接地阈值：句子与来源切片最大 embedding 相似度低于该值 → 未接地。
    # 默认 0.6 为 bge-small-zh-v1.5 实测标定值（B5-b：逐句相似度中位数 ≈0.73，
    # 接地句多落 0.6-0.9，文档示例 0.75 会把 ~62% 真实接地句误判为幻觉）；
    # 按 15.3「阈值可在配置中调整」，.env 经 GROUNDING_THRESHOLD 可覆盖。
    grounding_threshold: float = 0.6

    # 数据库（B1）：SQLite 嵌入式，相对 backend/ 工作目录
    database_url: str = "sqlite:///./zhixue.db"

    # JWT（B1）：HS256；demo 默认密钥，生产经 .env 覆盖
    jwt_secret: str = "zhixue-dev-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = 7200  # 登录响应 expiresIn 与之一致

    # RAG 管道（B3）：本地模型 + Chroma 持久化，均带默认值（无网络/无模型也降级可跑）
    # 向量库 / 模型缓存目录（相对 backend/ 工作目录）
    chroma_dir: str = "./data/chroma"
    model_cache_dir: str = "./data/models"
    # 本地模型名（sentence-transformers 自动下载到 model_cache_dir；加载失败自动降级）
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    reranker_model_name: str = "BAAI/bge-reranker-base"
    # 降级哈希嵌入维度（embedding 模型不可用时启用，保证全链路可跑）
    embedding_fallback_dim: int = 256
    # 切片参数（需求文档 4.3.1）
    chunk_size: int = 512
    chunk_overlap: int = 64
    # 混合检索 RRF 权重（需求文档 4.3.2）
    rrf_dense_weight: float = 0.7
    rrf_sparse_weight: float = 0.3
    rrf_k: int = 60

    # B7-a 实时通道演示参数：
    # - workflow_step_delay_ms：工作流节点间推进延迟，让 WS / 轮询能观察到 phase
    #   渐进点亮（mock 工作流毫秒级完成，无延迟时大屏一闪而过）；0 = 不延迟（测试用）
    # - tutor_stream_delay_ms：tutor mock 逐字流式的字间延迟（打字机演示效果）
    workflow_step_delay_ms: int = 500
    tutor_stream_delay_ms: int = 20

    # 岗位市场（B6 / 接口文档 15.5）：预置快照 JSON 目录（种子导入来源，相对 backend/）；
    # job_market_offline=True 模拟「实时数据源不可用」→ /job-market/{id} 走 2002 降级
    job_market_dir: str = "../frontend/public/data/job-market"
    job_market_offline: bool = False

    # 外部资源联网搜索（接口文档 8.6 增量，C-fix 批3-bonus）：可插拔搜索 provider。
    # - search_provider：none（无搜索能力，走种子兜底/offline）| tavily（Tavily Web Search API）；
    #   未来可扩展 serpapi / bing / youtube / arxiv，接口签名不变。
    # - search_api_key：对应 provider 的密钥（经 .env 注入；缺省为空 → 自动回落 offline 兜底）。
    # 缺省 none，无密钥也能跑（mock/种子兜底，CLAUDE.md 纪律）。
    search_provider: str = "none"
    search_api_key: str = ""
    search_base_url: str = "https://api.tavily.com"
    search_timeout_seconds: float = 12.0
    search_max_results: int = 8

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        """允许 .env 用逗号分隔字符串配置 CORS_ORIGINS。"""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


settings = Settings()
