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
from app.schemas.auth import ForgotPasswordRequest, LoginRequest, RegisterRequest
from app.services import users as users_service

router = APIRouter(tags=["auth"])


def _auth_payload(user: User, db: Session) -> dict:
    """签发 token 并拼装登录/注册一致的响应 data（接口文档 3.1 / 15.1 / 16.1）。"""
    journey = db.get(Journey, user.id)
    token, expires_in = create_access_token(user.id, user.role)
    return {
        "token": token,
        "expiresIn": expires_in,
        "user": {
            "userId": user.id,
            "username": user.username,
            "displayName": user.display_name,
            "role": user.role,
            "hasDiagnosed": bool(journey.has_diagnosed) if journey else False,
            "hasGeneratedPath": bool(journey.has_generated_path) if journey else False,
        },
    }


@router.post("/auth/login")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """登录。用户名/口令错误 → 1002（401）；账号被禁用 → 1002（401，接口文档 16.0）。"""
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        return fail(code=1002, message="用户名或密码错误", status_code=401)
    if not bool(user.is_active):
        return fail(code=1002, message="账号已禁用", status_code=401)

    users_service.touch_last_active(db, user)  # 刷新最近活跃（16.2）
    return success(_auth_payload(user, db))


@router.post("/auth/register")
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """注册（接口文档 16.1）。查重/弱密码 → 1001；成功直接返回 login 同构 token+user。"""
    try:
        user = users_service.create_learner(db, body.username, body.password)
    except users_service.UserServiceError as err:
        return fail(code=err.code, message=err.message, status_code=err.status_code)
    users_service.touch_last_active(db, user)
    return success(_auth_payload(user, db))


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
