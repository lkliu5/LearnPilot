"""画像诊断模块 Profile（接口文档第 4 章，B2-a）。

接口 4/5/6/7：
- POST /profile/parse           多模态材料解析（multipart）
- POST /profile/narrative       画像叙述生成（无材料返回 null）
- POST /profile/diagnosis-complete  完成诊断，写旅程
- GET  /profile/ability-portrait    能力雷达 6 维

均需登录（get_current_user）。生成调用经 LLMClient（在 service 层）；
真实模式 LLM 失败 → 2001 / HTTP 500（B5-b，接口文档 1.3）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import fail, success
from app.core.llm import LLMGenerationError
from app.core.security import get_current_user
from app.models.entities import User
from app.schemas.profile import DiagnosisCompleteRequest, NarrativeRequest
from app.services import profile as profile_service

router = APIRouter(tags=["profile"])


@router.post("/profile/parse")
async def parse(
    files: list[UploadFile] | None = File(default=None),
    description: str | None = Form(default=None),
    user: User = Depends(get_current_user),
):
    """多模态材料解析（接口文档 4.1）。files/description 均可空。"""
    uploads: list[tuple[str, bytes]] = []
    for f in files or []:
        if not f.filename:
            continue
        uploads.append((f.filename, await f.read()))
    try:
        data = profile_service.parse_profile(user, uploads, description)
    except LLMGenerationError as exc:
        return fail(code=2001, message=f"LLM/Agent 生成失败：{exc}", status_code=500)
    return success(data)


@router.post("/profile/narrative")
async def narrative(
    body: NarrativeRequest,
    user: User = Depends(get_current_user),
):
    """画像叙述生成（接口文档 4.2）。无材料 → data 为 null。"""
    try:
        data = profile_service.generate_narrative(body)
    except LLMGenerationError as exc:
        return fail(code=2001, message=f"LLM/Agent 生成失败：{exc}", status_code=500)
    return success(data)


@router.post("/profile/diagnosis-complete")
async def diagnosis_complete(
    body: DiagnosisCompleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """完成诊断，写入旅程状态（接口文档 4.3）。"""
    data = profile_service.complete_diagnosis(db, user, body)
    return success(data)


@router.get("/profile/ability-portrait")
async def ability_portrait(user: User = Depends(get_current_user)):
    """能力雷达数据（接口文档 4.4）。"""
    data = profile_service.ability_portrait(user)
    return success(data)
