"""FastAPI 应用入口。

B0：CORS + traceId 中间件 + 统一信封异常处理 + 挂载 /api/v1 路由。
B1：启动时初始化数据库 + 种子 + 日志脱敏；挂载 auth / admin 路由。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import (
    admin,
    admin_kb,
    admin_metrics,
    admin_prompts,
    auth,
    dashboard,
    health,
    job_market,
    knowledge_graph,
    learning_path,
    mastery,
    profile,
    quiz,
    resource,
    tasks,
)
from app.core.config import settings
from app.core.envelope import (
    TraceIdMiddleware,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.init_db import init_db
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：装脱敏过滤器 + 建表灌种子（幂等）
    setup_logging()
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

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
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
# B2-a：Profile / LearningPath / Task
app.include_router(profile.router, prefix=settings.api_prefix)
app.include_router(learning_path.router, prefix=settings.api_prefix)
app.include_router(tasks.router, prefix=settings.api_prefix)
# B2-b：Mastery & Journey / Resource / Quiz
app.include_router(mastery.router, prefix=settings.api_prefix)
app.include_router(resource.router, prefix=settings.api_prefix)
app.include_router(quiz.router, prefix=settings.api_prefix)
# B3：管理端知识库 RAG 四件套
app.include_router(admin_kb.router, prefix=settings.api_prefix)
# B4-b：管理端 Prompt 热更新 + 指标看板
app.include_router(admin_prompts.router, prefix=settings.api_prefix)
app.include_router(admin_metrics.router, prefix=settings.api_prefix)
# B6：P1 特色——岗位市场 / 知识图谱 / 学情概览（Reinforce 在 quiz、External 在 resource）
app.include_router(job_market.router, prefix=settings.api_prefix)
app.include_router(knowledge_graph.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)
