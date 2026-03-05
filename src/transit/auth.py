"""
认证模块
实现基于 token 的认证功能
"""

from fastapi import HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from .config import settings


# 定义安全方案
security = HTTPBearer(auto_error=False)


async def verify_write_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    """
    验证写 token（用于上传文件）

    Args:
        request: 请求对象
        credentials: 认证凭据

    Returns:
        token 字符串，如果认证未启用则返回 None

    Raises:
        HTTPException: 认证失败时抛出 401 错误
    """
    # 如果未启用认证，直接返回
    if not settings.auth_enabled:
        return None

    # 检查是否提供了 token
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 验证 token 是否在写 token 列表中
    if token not in settings.write_token_list:
        raise HTTPException(
            status_code=401,
            detail="Invalid write token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


async def verify_read_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    """
    验证读 token（用于下载文件和查询元信息）

    Args:
        request: 请求对象
        credentials: 认证凭据

    Returns:
        token 字符串，如果认证未启用则返回 None

    Raises:
        HTTPException: 认证失败时抛出 401 错误
    """
    # 如果未启用认证，直接返回
    if not settings.auth_enabled:
        return None

    # 检查是否提供了 token
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 验证 token 是否在读 token 列表中
    if token not in settings.read_token_list:
        raise HTTPException(
            status_code=401,
            detail="Invalid read token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token
