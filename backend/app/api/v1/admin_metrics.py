"""管理端系统指标看板接口（B4-b，接口文档 14.6）。

GET /admin/metrics —— 供前端三 gauge 仪表盘（CountUp）消费。

结构按契约定死：三比率 + 三计数 + updatedAt。
- 三比率（hallucinationRate/adaptationRate/coverageRate）当前为占位常量
  （取接口文档 14.6 示例值），B8 接入真实计算（15.3 逐句接地口径 + 统计脚本），
  仅替换取值逻辑、结构不变；
- 三计数为 DB 实时统计：知识库文档数 / 切片总数 / 已生成资源数。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import success
from app.core.security import require_admin
from app.models.entities import KnowledgeDocument, ResourceCache, User

router = APIRouter(tags=["admin-metrics"])

# B8 前的占位比率（接口文档 14.6 示例值；目标：幻觉率 <0.05、适配率 ≥0.85、覆盖率 ≥0.90）
_PLACEHOLDER_RATES = {
    "hallucinationRate": 0.021,
    "adaptationRate": 0.87,
    "coverageRate": 0.92,
}


@router.get("/admin/metrics")
async def get_metrics(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """系统指标看板（接口文档 14.6）。"""
    kb_documents = db.query(func.count(KnowledgeDocument.id)).scalar() or 0
    kb_chunks = db.query(func.coalesce(func.sum(KnowledgeDocument.chunks), 0)).scalar() or 0
    generated_resources = db.query(func.count(ResourceCache.id)).scalar() or 0
    return success(
        {
            **_PLACEHOLDER_RATES,
            "kbDocuments": int(kb_documents),
            "kbChunks": int(kb_chunks),
            "generatedResources": int(generated_resources),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
