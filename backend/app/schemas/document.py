"""「文档学习」请求体（接口文档第 20 章）。

上传走 multipart（UploadFile，见 api/v1/document.py），生成类走 JSON body。
字段 camelCase 对齐前端；难度枚举复用讲义档（入门|初级|中级|高级|精通）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DocLectureRequest(BaseModel):
    documentId: str = Field(..., min_length=1)
    difficulty: str = "初级"


class DocVideoRequest(BaseModel):
    documentId: str = Field(..., min_length=1)
    difficulty: str = "初级"


class DocOverviewRequest(BaseModel):
    documentId: str = Field(..., min_length=1)


class DocDiagramRequest(BaseModel):
    documentId: str = Field(..., min_length=1)


class DocMindmapRequest(BaseModel):
    documentId: str = Field(..., min_length=1)


class DocQuizRequest(BaseModel):
    documentId: str = Field(..., min_length=1)
    count: int = Field(default=5, ge=1, le=20)


class DocFlashcardRequest(BaseModel):
    documentId: str = Field(..., min_length=1)
    count: int = Field(default=8, ge=1, le=30)
