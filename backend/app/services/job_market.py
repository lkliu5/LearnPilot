"""岗位市场服务（B6）。

覆盖接口文档第 5 章 / 15.5 数据管线约定：
- 5.1 hot_jobs：热门岗位列表 [{id, name}]，固定契约顺序（种子 sort_order）。
- 5.2 get_snapshot：岗位市场快照（2.4 JobMarket 完整结构）。
  - demo 阶段：后端托管预置快照（种子自 frontend/public/data/job-market/*.json），
    JobSnapshot 表即数据源；
  - 降级（15.5）：实时数据源不可用（settings.job_market_offline 模拟故障开关）→
    返回最近快照并置 code 2002 / data.offline=true（HTTP 200），对齐前端
    JobMarketResult.offline「离线快照」标记；
  - 生产路径：离线采集管线（聚合 BOSS直聘/拉勾/智联公开 JD 样本 + LLM 抽取
    技能频率与雷达维度）定期刷新 JobSnapshot，接口签名不变（写 README，不在 demo 实现）。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import JobSnapshot


class UnknownJob(Exception):
    """岗位不存在（→ code 1004 / 404）。"""


def hot_jobs(db: Session) -> list[dict[str, str]]:
    """热门岗位列表（接口文档 5.1）。按种子 sort_order（契约示例序）排序。"""
    rows = (
        db.query(JobSnapshot)
        .order_by(JobSnapshot.sort_order, JobSnapshot.id)
        .all()
    )
    return [{"id": row.id, "name": row.name} for row in rows]


def get_snapshot(db: Session, job_id: str) -> tuple[dict[str, Any], bool]:
    """岗位市场快照（接口文档 5.2）。返回 (payload, offline)。

    - 数据源正常：返回 (JobMarket, False)，路由套 code 0；
    - 数据源不可用（job_market_offline=True 模拟）：返回最近快照
      (JobMarket + offline:true, True)，路由套 code 2002（降级而非 500）；
    - 岗位不存在（含降级时无任何快照可回退）：抛 UnknownJob → 1004。
    """
    row = db.get(JobSnapshot, job_id)
    if row is None:
        raise UnknownJob(job_id)
    payload = dict(row.payload)
    if settings.job_market_offline:
        # 最近快照 + 离线标记（payload.fetchedAt 不变，前端 timeAgo 显示快照年龄）
        payload["offline"] = True
        return payload, True
    return payload, False
