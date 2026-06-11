"""学情概览模块 Dashboard（接口文档第 12 章，B6）。

接口 29：
- GET /dashboard/overview  聚合 mastery/journey/雷达/强弱项（与明细接口口径严格一致）

需登录。环境上下文卡片（时钟/天气/贴士）为前端本地生成，无后端接口（12.1 备注）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import success
from app.core.security import get_current_user
from app.models.entities import User
from app.services import dashboard as dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/overview")
async def dashboard_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """学情概览聚合数据（接口文档 12.1）。"""
    return success(dashboard_service.overview(db, user))
