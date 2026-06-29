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

    # 讲义真实配图「图片搜索 provider」（app/services/image_search.py）：与上面的文本搜索
    # （Tavily 等）解耦，专走**免版权、URL 稳定、可标注来源**的图源，替换掉之前 Tavily 图片那条
    # 带防盗链 / 会过期 CDN 链接（byteimg）导致「图片暂不可用」的路。
    # - image_provider：none（不插真实图）| wikimedia（默认，Wikimedia Commons，免密钥）| pexels（需 Key）；
    # - wikimedia_api_url：Commons MediaWiki API 入口（免密钥，联网即可用）；
    # - pexels_api_key / pexels_base_url：预留兜底图源（配 Key 即作为 Wikimedia 没命中时的 fallback）；
    # - image_search_timeout_seconds / image_search_max_results：单次搜图超时与候选条数。
    # 缺省 wikimedia：真实 LLM 模式联网取真实图；mock 模式由 lecture_media 拦截走占位、不调本模块
    # （无任何 Key 仍跑通全链路，CLAUDE.md 纪律）。
    image_provider: str = "wikimedia"
    wikimedia_api_url: str = "https://commons.wikimedia.org/w/api.php"
    pexels_api_key: str = ""
    pexels_base_url: str = "https://api.pexels.com"
    image_search_timeout_seconds: float = 12.0
    image_search_max_results: int = 8

    # 语音合成 TTS（讲解视频/导学旁白配音，移植自桌面端 voice.py 的合成逻辑，Web 化）：
    # - tts_provider：edge（默认，edge-tts 微软神经语音，联网免密钥）| none（禁用 → 前端回落浏览器 TTS）；
    # - tts_voice / tts_rate / tts_pitch：默认自然中文女声 XiaoyiNeural（语速 -10%、音调 +2Hz）；
    # - tts_cache_dir：以 md5(text+voice+rate+pitch) 为键缓存 MP3，命中直接返回（目录入 .gitignore）；
    # - tts_timeout / tts_max_retries：单次合成超时与重试兜底；联网失败优雅降级（返回 2002，不崩）。
    # 缺省 edge，但无网/合成失败自动降级，Mock/无密钥仍跑通全链路（CLAUDE.md 纪律）。
    tts_provider: str = "edge"
    tts_voice: str = "zh-CN-XiaoyiNeural"
    tts_rate: str = "-10%"
    tts_pitch: str = "+2Hz"
    tts_cache_dir: str = "./data/tts_cache"
    tts_timeout_seconds: float = 20.0
    tts_max_retries: int = 3
    tts_max_chars: int = 2000  # 单次合成文本上限（防超长滥用）

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        """允许 .env 用逗号分隔字符串配置 CORS_ORIGINS。"""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


settings = Settings()
