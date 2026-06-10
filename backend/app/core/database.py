"""SQLAlchemy 引擎 / 会话 / Base（B1）。

轻量栈：SQLite 嵌入式（CLAUDE.md 约定，不引入 PostgreSQL）。
- engine：单文件 SQLite，`check_same_thread=False` 适配 FastAPI 多线程依赖；
- SessionLocal：请求级会话工厂；
- Base：所有 ORM 模型的声明基类；
- get_db：FastAPI 依赖，保证会话开闭。
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

# SQLite 需 check_same_thread=False 才能跨线程复用连接
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：产出一个请求级会话，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
