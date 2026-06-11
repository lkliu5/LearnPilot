"""岗位市场模块 Job Market（接口文档第 5 章，B6）。

接口 8/9：
- GET /job-market/hot   热门岗位列表 [{id, name}]
- GET /job-market/{id}  岗位市场快照（2.4 JobMarket；数据源不可用 → 2002 降级）

均需登录。岗位不存在 → 1004；降级回包 code 2002 + data.offline=true（HTTP 200）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import fail, success
from app.core.security import get_current_user
from app.models.entities import User
from app.services import job_market as job_market_service

router = APIRouter(tags=["job-market"])


@router.get("/job-market/hot")
async def hot_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """热门岗位列表（接口文档 5.1）。"""
    return success(job_market_service.hot_jobs(db))


@router.get("/job-market/{job_id}")
async def job_snapshot(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """岗位市场快照（接口文档 5.2）。降级时 code 2002 + offline:true（非 500）。"""
    try:
        payload, offline = job_market_service.get_snapshot(db, job_id)
    except job_market_service.UnknownJob:
        return fail(code=1004, message="岗位不存在", status_code=404)
    if offline:
        return fail(
            code=2002,
            message="岗位实时数据源不可用，已降级返回最近快照",
            data=payload,
            status_code=200,
        )
    return success(payload)
