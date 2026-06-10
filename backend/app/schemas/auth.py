"""Auth 请求体 schema（B1）。

仅约束入参；响应统一经 app.core.envelope.success 包裹为信封，故响应体用普通 dict
按接口文档 3.1 / 15.1 拼装（含 camelCase 字段名），不在此定义响应模型。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    remember: bool = False  # 可选


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=1)
