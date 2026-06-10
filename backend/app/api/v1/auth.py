"""认证模块 Auth（接口文档第 3 章 + 15.1）。

接口 1/2/3：
- POST /auth/login —— 校验口令，签发 JWT，响应含 role + hasDiagnosed + hasGeneratedPath；
- POST /auth/forgot-password —— 占位，返回 {sent:true}；
- POST /auth/logout —— 令当前 token 失效（jti 入黑名单）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.envelope import fail, success
from app.core.security import (
    _current_payload,
    create_access_token,
    revoke_token,
    verify_password,
)
from app.models.entities import Journey, User
from app.schemas.auth import ForgotPasswordRequest, LoginRequest

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """登录。用户名/口令错误 → code 1002（401）。"""
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        return fail(code=1002, message="用户名或密码错误", status_code=401)

    journey = db.get(Journey, user.id)
    has_diagnosed = bool(journey.has_diagnosed) if journey else False
    has_generated_path = bool(journey.has_generated_path) if journey else False

    token, expires_in = create_access_token(user.id, user.role)
    return success(
        {
            "token": token,
            "expiresIn": expires_in,
            "user": {
                "userId": user.id,
                "username": user.username,
                "displayName": user.display_name,
                "role": user.role,
                "hasDiagnosed": has_diagnosed,
                "hasGeneratedPath": has_generated_path,
            },
        }
    )


@router.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    """找回密码占位（不泄露账号是否存在）。"""
    return success({"sent": True})


@router.post("/auth/logout")
async def logout(payload: dict = Depends(_current_payload)):
    """退出登录：当前令牌 jti 入黑名单，后续携带即 1002。"""
    jti = payload.get("jti")
    if jti:
        revoke_token(jti)
    return success({"loggedOut": True})
