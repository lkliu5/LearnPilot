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
    )

    # 应用元信息
    app_name: str = "智学中枢后端"
    api_prefix: str = "/api/v1"

    # CORS 允许来源（默认放行前端 Vite 3000/3001）
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # LLM Provider（mock / deepseek / qwen / anthropic）—— B0 仅占位
    llm_provider: str = "mock"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        """允许 .env 用逗号分隔字符串配置 CORS_ORIGINS。"""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


settings = Settings()
