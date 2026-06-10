"""FastAPI 应用入口。

B0：CORS + traceId 中间件 + 统一信封异常处理 + 挂载 /api/v1 路由。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import health
from app.core.config import settings
from app.core.envelope import (
    TraceIdMiddleware,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)

app = FastAPI(title=settings.app_name)

# CORS（暴露 X-Trace-Id 便于前端排查）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-Id"],
)

# traceId 注入（CORS 之后添加 → 请求时先于 CORS 执行，保证响应头写入）
app.add_middleware(TraceIdMiddleware)

# 统一信封异常处理
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# 路由挂载
app.include_router(health.router, prefix=settings.api_prefix)
