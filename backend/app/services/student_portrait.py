"""异质学生动态画像存储服务（接口文档 17.2 / 17.3，C1-b）。

- 每用户一行 StudentPortrait（user_id PK），dimensions 存 PortraitDimension[]；
- get-or-create：首次访问落空画像（dimensions=[]），17.3「尚未开始诊断」占位，
  不视为错误；
- apply_updates：按 key 合并（随学随新）——同 key 字段级覆盖（新值覆盖旧值，
  未给字段保留旧值，如仅更新 value 不丢历史 score），新 key 追加；每维写
  updatedAt，整体 updated_at 刷新；维度按 PORTRAIT_DIMENSIONS 顺序稳定排列。

与 4.4 ability-portrait（固定 6 知识点雷达）并存、互不替换——本服务不读写
那条链路（_portrait_by_user 内存缓存），二者数据结构与用途均不同。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.llm import PORTRAIT_DIMENSIONS
from app.models.entities import StudentPortrait

_ORDER: dict[str, int] = {k: i for i, (k, _) in enumerate(PORTRAIT_DIMENSIONS)}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(row: StudentPortrait) -> dict[str, Any]:
    """StudentPortrait → 接口文档 17.2 响应 data（camelCase）。"""
    return {
        "dimensions": list(row.dimensions or []),
        "version": row.version or "v1",
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _get_or_create(db: Session, user_id: str) -> StudentPortrait:
    """取/建画像行（幂等）。首次访问落空画像（dimensions=[]）。"""
    row = db.get(StudentPortrait, user_id)
    if row is None:
        row = StudentPortrait(user_id=user_id, dimensions=[], version="v1")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_portrait(db: Session, user_id: str) -> dict[str, Any]:
    """获取当前最新画像（接口文档 17.3）。无数据 → 空画像占位。"""
    return _serialize(_get_or_create(db, user_id))


def apply_updates(
    db: Session, user_id: str, updates: list[dict[str, Any]]
) -> dict[str, Any]:
    """合并画像维度增量并持久化（接口文档 17.2「随学随新」）。

    updates: 已经过 LLMClient 契约清洗的 PortraitDimension[]（无 updatedAt）。
    返回合并后的完整画像（17.2 结构）。
    """
    row = _get_or_create(db, user_id)
    by_key: dict[str, dict[str, Any]] = {d["key"]: dict(d) for d in (row.dimensions or [])}
    stamp = _now_iso()
    for upd in updates:
        key = upd.get("key")
        if not key:
            continue
        merged = by_key.get(key, {})
        # 字段级覆盖：新增量提供的字段覆盖旧值，未提供的字段保留（如仅更 value 不丢 score）
        merged.update({k: v for k, v in upd.items() if v is not None})
        merged["updatedAt"] = stamp
        by_key[key] = merged

    # 按固定维度顺序稳定排列（未知 key 落到末尾，保持插入序）
    dimensions = sorted(by_key.values(), key=lambda d: _ORDER.get(d["key"], len(_ORDER)))
    row.dimensions = dimensions
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _serialize(row)
