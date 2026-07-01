"""「文档学习」接口（接口文档第 20 章）。

平行独立线：上传自己的文档 → 解析入**专属向量集合**（隔离内置知识库）→ 基于文档生成
讲义/视频/图解/思维导图/练习题/闪卡 → 进「我的资源库」（带文档来源标识）。全部 require 登录，
文档归属校验（仅能操作本人文档）。绝不改动内置课程主线。

- POST   /document/upload                multipart 上传（pdf/txt/md/docx），异步入库，返回 taskId
- GET    /document/list                  当前用户文档列表
- GET    /document/{docId}               文档详情（含解析文本预览）
- DELETE /document/{docId}               删除文档 + 专属向量集合
- POST   /document/generate/lecture      基于文档生成讲义
- POST   /document/generate/video        基于文档生成视频分镜
- POST   /document/generate/diagram      基于文档生成 Mermaid 图解
- POST   /document/generate/mindmap      基于文档生成思维导图（Markmap）
- POST   /document/generate/quiz         基于文档生成练习题
- POST   /document/generate/flashcards   基于文档生成闪卡
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import fail, success
from app.core.security import get_current_user
from app.models.entities import User
from app.schemas.document import (
    DocDiagramRequest,
    DocFlashcardRequest,
    DocLectureRequest,
    DocMindmapRequest,
    DocQuizRequest,
    DocVideoRequest,
)
from app.services import document_generation as gen
from app.services import document_parse, document_store

router = APIRouter(tags=["document-learning"])


# ---- 文档管理 --------------------------------------------------------------
@router.post("/document/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传文档（接口文档 20.1）。解析 + 异步入专属向量集合，返回 taskId + document。"""
    if not file.filename:
        return fail(code=1001, message="未提供有效文件", status_code=400)
    raw = await file.read()
    if not raw:
        return fail(code=1001, message="文件内容为空", status_code=400)
    try:
        data = document_store.upload_document(db, user.id, file.filename, raw)
    except document_parse.UnsupportedDocument as exc:
        return fail(
            code=1001,
            message=f"不支持的文档格式：{exc}（仅支持 PDF / 文本 / Markdown / Word）",
            status_code=400,
        )
    return success(data)


@router.get("/document/list")
async def list_my_documents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户文档列表（接口文档 20.2）。"""
    return success(document_store.list_documents(db, user.id))


@router.get("/document/{doc_id}")
async def get_my_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """文档详情（接口文档 20.3）。非本人/不存在 → 1004。"""
    try:
        return success(document_store.get_document(db, user.id, doc_id))
    except document_store.UnknownDocument:
        return fail(code=1004, message="文档不存在", status_code=404)


@router.delete("/document/{doc_id}")
async def delete_my_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除文档及其专属向量集合（接口文档 20.4）。非本人/不存在 → 1004。"""
    try:
        return success(document_store.delete_document(db, user.id, doc_id))
    except document_store.UnknownDocument:
        return fail(code=1004, message="文档不存在", status_code=404)


# ---- 基于文档生成（复用现有引擎） ------------------------------------------
def _guarded_generate(fn, *args):
    """把服务层的领域异常统一转信封（1004 文档不存在 / 1001 未就绪或参数非法）。"""
    try:
        return success(fn(*args))
    except document_store.UnknownDocument:
        return fail(code=1004, message="文档不存在", status_code=404)
    except gen.DocumentNotReady:
        return fail(code=1001, message="文档尚未完成解析入库，请稍后重试", status_code=400)
    except gen.InvalidDifficulty:
        return fail(code=1001, message="难度档非法", status_code=400)


@router.post("/document/generate/lecture")
async def gen_lecture(
    body: DocLectureRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于文档生成讲义（接口文档 20.5.1）。"""
    return _guarded_generate(gen.generate_lecture, db, user.id, body.documentId, body.difficulty)


@router.post("/document/generate/video")
async def gen_video(
    body: DocVideoRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于文档生成视频分镜（接口文档 20.5.2）。"""
    return _guarded_generate(gen.generate_video, db, user.id, body.documentId, body.difficulty)


@router.post("/document/generate/diagram")
async def gen_diagram(
    body: DocDiagramRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于文档生成 Mermaid 图解（接口文档 20.5.3）。"""
    return _guarded_generate(gen.generate_diagram, db, user.id, body.documentId)


@router.post("/document/generate/mindmap")
async def gen_mindmap(
    body: DocMindmapRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于文档生成思维导图（接口文档 20.5.4）。"""
    return _guarded_generate(gen.generate_mindmap, db, user.id, body.documentId)


@router.post("/document/generate/quiz")
async def gen_quiz(
    body: DocQuizRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于文档生成练习题（接口文档 20.6）。"""
    return _guarded_generate(gen.generate_quiz, db, user.id, body.documentId, body.count)


@router.post("/document/generate/flashcards")
async def gen_flashcards(
    body: DocFlashcardRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于文档生成闪卡（接口文档 20.7）。"""
    return _guarded_generate(gen.generate_flashcards, db, user.id, body.documentId, body.count)
