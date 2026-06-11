"""学习资源模块 Resource（接口文档第 8 章前两接口，B2-b）。

接口 16/17：
- GET  /resource/knowledge-point/{kpId}  知识点元信息 { id,name,description,status }
- POST /resource/lecture                  自适应讲义（markdown+sources+hallucinationRate）

均需登录。生成走 service → LLMClient（mock 确定性 / deepseek 真实工作流）。
知识点不存在 → 1004；讲义难度档非法 → 1001；LLM/Agent 生成失败 → 2001（B5-b）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import fail, success
from app.core.llm import LLMGenerationError
from app.core.security import get_current_user
from app.models.entities import User
from app.schemas.resource import LectureRequest
from app.services import resource as resource_service

router = APIRouter(tags=["resource"])


@router.get("/resource/knowledge-point/{kp_id}")
async def knowledge_point_meta(
    kp_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """知识点元信息（接口文档 8.1）。"""
    try:
        data = resource_service.knowledge_point_meta(db, user.id, kp_id)
    except resource_service.UnknownKnowledgePoint:
        return fail(code=1004, message="知识点不存在", status_code=404)
    return success(data)


@router.post("/resource/lecture")
async def generate_lecture(
    body: LectureRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成自适应讲义（接口文档 8.2）。"""
    try:
        data = resource_service.generate_lecture(db, user.id, body.kpId, body.difficulty)
    except resource_service.UnknownKnowledgePoint:
        return fail(code=1004, message="知识点不存在", status_code=404)
    except resource_service.InvalidDifficulty:
        return fail(code=1001, message="难度档非法，应为 入门|初级|高级", status_code=400)
    except LLMGenerationError as exc:
        return fail(code=2001, message=f"LLM/Agent 生成失败：{exc}", status_code=500)
    return success(data)
