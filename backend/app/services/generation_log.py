"""用户资源生成历史服务（「我的资源库」）。

两件事：
- ``record()``：生成/获取一类资源成功后**追加式埋点**（旁路，绝不打断生成主链路）。
  去重口径见 GenerationLog 文档——同一 (user_id,kp_id,kind,difficulty) upsert 刷新时间。
- ``list_history()``：按用户分页列出其资产，支持按 kind / 知识点 / 时间过滤，回 kpName。

kind 归一化：ResourceCache 的 kind 可能带 ``@provider`` / ``#tier`` 后缀（如
``lecture@deepseek#advanced``），本表只存基类（``lecture``），保证「一种资产一行」、
与切换 provider / 个性化档无关。非五类白名单的 kind 一律忽略（record 静默 no-op）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import GenerationLog, KnowledgePoint

logger = logging.getLogger(__name__)

# 五类可入库资产（归一化基类）→ 展示用中文形态名
KIND_LABELS: dict[str, str] = {
    "lecture": "定制讲义",
    "video": "讲解视频",
    "diagram": "知识图解",
    "mindmap": "思维导图",
    "code": "代码实操",
}
ALLOWED_KINDS = set(KIND_LABELS)


def normalize_kind(kind: str) -> str:
    """剥离 ResourceCache 的 provider/tier 后缀，取基类（lecture@deepseek#advanced→lecture）。"""
    return (kind or "").split("@", 1)[0].split("#", 1)[0].strip()


def _default_title(db: Session, kp_id: str, kind: str, difficulty: str) -> str:
    """默认展示标题：「<知识点名> · <形态>[（难度）]」。"""
    kp = db.get(KnowledgePoint, kp_id)
    name = kp.name if kp else kp_id
    label = KIND_LABELS.get(kind, kind)
    return f"{name} · {label}（{difficulty}）" if difficulty else f"{name} · {label}"


def record(
    db: Session,
    user_id: str,
    kp_id: str,
    kind: str,
    difficulty: str = "",
    *,
    title: str | None = None,
    resource_ref: str | None = None,
) -> None:
    """追加式埋点（upsert）。**任何异常都吞掉**——埋点失败绝不能拖垮资源生成主链路。

    - kind 归一化到五类基类，非白名单直接忽略；
    - 命中 (user_id,kp_id,kind,difficulty) → 刷新 created_at（+可选 title/ref），
      否则插入新行；
    - 用 flush 探测唯一冲突（并发下双插入），冲突则回退为更新既有行。
    """
    if not user_id or not kp_id:
        return
    base_kind = normalize_kind(kind)
    if base_kind not in ALLOWED_KINDS:
        return
    diff = difficulty or ""
    try:
        row = (
            db.query(GenerationLog)
            .filter(
                GenerationLog.user_id == user_id,
                GenerationLog.kp_id == kp_id,
                GenerationLog.kind == base_kind,
                GenerationLog.difficulty == diff,
            )
            .one_or_none()
        )
        now = datetime.now(timezone.utc)
        ref = resource_ref if resource_ref is not None else f"{base_kind}:{kp_id}:{diff}"
        ttl = title if title else _default_title(db, kp_id, base_kind, diff)
        if row is not None:
            row.created_at = now  # 最近生成时间
            row.title = ttl
            row.resource_ref = ref
        else:
            db.add(
                GenerationLog(
                    user_id=user_id,
                    kp_id=kp_id,
                    kind=base_kind,
                    difficulty=diff,
                    title=ttl,
                    resource_ref=ref,
                    created_at=now,
                )
            )
        db.commit()
    except Exception as exc:  # noqa: BLE001  埋点旁路：失败仅告警，不外抛
        db.rollback()
        logger.warning("[generation_log] 埋点失败（已忽略）：%s", exc)


def _iso_utc(dt: datetime | None) -> str | None:
    """把落库的（naive）UTC 时间显式标注为 UTC 再 isoformat，避免前端按本地时区误解出现时差。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_time(value: str | None) -> datetime | None:
    """宽松解析时间过滤参数：接受 ISO8601（含带 Z）或 YYYY-MM-DD。解析失败→None（不过滤）。"""
    if not value:
        return None
    raw = value.strip().replace("Z", "+00:00")
    parsed: datetime | None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.strptime(value.strip()[:10], "%Y-%m-%d")
        except ValueError:
            return None
    # 落库列为 naive-UTC；带时区的入参统一折算到 UTC 再去 tz，保证与列同口径可比
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def list_history(
    db: Session,
    user_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
    kind: str | None = None,
    kp_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """分页列出当前用户的资源生成历史（按生成时间倒序），附知识点名。

    过滤：kind（五类基类）/ kpId / 时间区间 [startTime, endTime]。返回契约字段 camelCase。
    """
    q = db.query(GenerationLog).filter(GenerationLog.user_id == user_id)
    base_kind = normalize_kind(kind) if kind else None
    if base_kind in ALLOWED_KINDS:
        q = q.filter(GenerationLog.kind == base_kind)
    if kp_id:
        q = q.filter(GenerationLog.kp_id == kp_id)
    start = _parse_time(start_time)
    end = _parse_time(end_time)
    if start is not None:
        q = q.filter(GenerationLog.created_at >= start)
    if end is not None:
        q = q.filter(GenerationLog.created_at <= end)

    total = q.count()
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    rows = (
        q.order_by(GenerationLog.created_at.desc(), GenerationLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    # 一次取全部知识点名映射，避免逐行查库
    names = {kp.id: kp.name for kp in db.query(KnowledgePoint).all()}
    items = [
        {
            "id": r.id,
            "kpId": r.kp_id,
            "kpName": names.get(r.kp_id, r.kp_id),
            "kind": r.kind,
            "difficulty": r.difficulty,
            "title": r.title,
            "resourceRef": r.resource_ref,
            "createdAt": _iso_utc(r.created_at),
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "pageSize": page_size}
