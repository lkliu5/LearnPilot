"""生成模型管理接口（接口文档 21，additive 新增，不改任何既有接口）。

- GET /models          可选模型注册表 + 当前模型（登录即可：切换生成模型属用户级偏好）
- PUT /models/current  切换当前生成模型，后续所有生成走该模型；未知 id → 1001/400

切换仅改进程内运行态（app/core/model_registry.py），默认 = 既有 DeepSeek，
不切换则默认行为不变；未配 Key 的模型仍可选，调用时经 llm_transport 自动回落（绝不崩）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core import model_registry
from app.core.envelope import fail, success
from app.core.security import get_current_user
from app.models.entities import User

router = APIRouter(tags=["models"])


class ModelSwitchRequest(BaseModel):
    modelId: str = Field(..., min_length=1)


@router.get("/models")
async def list_models(user: User = Depends(get_current_user)):
    """可选生成模型列表 + 当前模型（接口文档 21.1）。"""
    return success(model_registry.snapshot())


@router.put("/models/current")
async def switch_model(
    body: ModelSwitchRequest,
    user: User = Depends(get_current_user),
):
    """切换当前生成模型（接口文档 21.2）。返回切换后的注册表快照。"""
    try:
        model_registry.set_current(body.modelId)
    except KeyError:
        return fail(code=1001, message=f"未知模型：{body.modelId}", status_code=400)
    return success(model_registry.snapshot())
