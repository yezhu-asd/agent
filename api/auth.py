"""
认证 API

提供手机号验证码、Token 登录、会话查询和退出登录接口。
"""

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from api.core.response_models import DataResponse
from services.auth_service import AuthError, auth_service


router = APIRouter(prefix="/api/auth", tags=["认证"])


class CodeRequest(BaseModel):
    phone: str = Field(..., description="手机号")


class LoginRequest(BaseModel):
    phone: str = Field(..., description="手机号")
    code: str = Field(..., description="验证码")
    user_name: Optional[str] = Field(default=None, description="用户姓名")
    role: str = Field(default="student", description="角色")
    grade_or_department: Optional[str] = Field(default=None, description="年级或院系")


def _extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Token 格式不正确")
    return parts[1].strip()


# 公共导出函数
def extract_token_from_header(authorization: Optional[str]) -> str:
    """从请求头中提取 Token"""
    return _extract_token(authorization)


def verify_token(token: str) -> dict:
    """验证 Token 并获取会话信息"""
    session = auth_service.get_session(token)
    if session is None:
        raise HTTPException(status_code=401, detail="未登录或 Token 已失效")
    return session


@router.post("/code", response_model=DataResponse, summary="获取验证码")
async def request_code(request: CodeRequest):
    try:
        payload = auth_service.request_verification_code(request.phone)
        return DataResponse(message="验证码生成成功", data=payload)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/login", response_model=DataResponse, summary="手机号验证码登录")
async def login(request: LoginRequest):
    try:
        payload = auth_service.login(
            phone=request.phone,
            code=request.code,
            user_name=request.user_name,
            role=request.role,
            grade_or_department=request.grade_or_department,
        )
        return DataResponse(message="登录成功", data=payload)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/me", response_model=DataResponse, summary="获取当前登录用户")
async def get_current_user(authorization: Optional[str] = Header(default=None)):
    token = _extract_token(authorization)
    session = auth_service.get_session(token)
    if session is None:
        raise HTTPException(status_code=401, detail="未登录或 Token 已失效")
    return DataResponse(message="获取成功", data=session)


@router.post("/logout", response_model=DataResponse, summary="退出登录")
async def logout(authorization: Optional[str] = Header(default=None)):
    token = _extract_token(authorization)
    auth_service.logout(token)
    return DataResponse(message="退出登录成功", data={"token": token})
