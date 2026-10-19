"""
认证模块
实现基于 token 的认证功能

预设 token 可从四个位置取用，按以下顺序命中第一个非空值：

1. `Authorization: Bearer <token>` 请求头（标准做法）
2. `X-Auth-Token: <token>` 请求头（代理/网关不转发 Authorization 时的备选）
3. 表单字段 `token`（multipart/form-data 或 x-www-form-urlencoded）
4. 查询参数 `?token=<token>`（不便设头或表单的客户端）

四种传法完全等价，都拿同一份 READ_TOKENS / WRITE_TOKENS 白名单校验。
"""

from typing import Optional

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

# 定义安全方案（auto_error=False：缺失时不直接拒绝，留给下面的多来源提取统一处理）
security = HTTPBearer(auto_error=False)


async def _extract_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[str]:
    """
    按优先级从请求中提取 token

    顺序：Authorization 头 → X-Auth-Token 头 → 表单 token → query token。
    只返回第一个非空值，不做校验；命中任何一个即视为“提供了凭据”。

    Args:
        request: 请求对象
        credentials: HTTPBearer 解出的凭据（可能为 None）

    Returns:
        提取到的 token；四处都没有时返回 None
    """
    # 1. Authorization: Bearer <token>（HTTPBearer 已解析）
    if credentials and credentials.credentials:
        return credentials.credentials

    # 2. X-Auth-Token 头
    header_token = request.headers.get("x-auth-token")
    if header_token:
        return header_token.strip()

    # 3. 查询参数 token（先于表单解析：命中即返回，不必碰请求体）
    query_token = request.query_params.get("token")
    if query_token:
        return query_token.strip()

    # 4. 表单字段 token
    #
    # ⚠️ 只有端点自身会解析表单时才读表单：PUT 裸 body 上传的文件就是这个 body，
    # 在此提前 await request.form() 会把流消费掉，上传端再读只剩 "Stream consumed"。
    # 判断依据是路由是否声明了表单参数——用 "请求体能不能当表单读" 不够（curl
    # --data-binary 默认就发 application/x-www-form-urlencoded，但那是文件内容）。
    if _endpoint_accepts_form(request):
        form = await request.form()
        raw = form.get("token")
        if isinstance(raw, str) and raw:
            return raw.strip()

    return None


def _endpoint_accepts_form(request: Request) -> bool:
    """
    判断当前路由是否声明了表单参数

    只有声明了 Form/File 参数的端点才会解析请求体为表单；其余端点（如 PUT 裸 body
    上传）的请求体是文件内容，读它就是破坏性操作。

    Args:
        request: 请求对象

    Returns:
        该路由是否接受表单
    """
    route = request.scope.get("route")
    if route is None:
        return False
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return False
    return bool(getattr(dependant, "body_params", None))


async def _require_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
    allowed: list[str],
    kind: str,
) -> Optional[str]:
    """
    提取并校验 token 的公共逻辑

    Args:
        request: 请求对象
        credentials: HTTPBearer 解出的凭据
        allowed: 允许的 token 列表
        kind: 凭据类型描述（"write" / "read"），用于错误信息

    Returns:
        校验通过的 token；认证未启用时返回 None

    Raises:
        HTTPException: 缺凭据或凭据不在白名单时抛 401
    """
    if not settings.auth_enabled:
        return None

    token = await _extract_token(request, credentials)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token not in allowed:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid {kind} token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


async def verify_write_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    """
    验证写 token（用于上传文件、发布页面）

    凭据可来自 Authorization 头 / X-Auth-Token 头 / 表单 token / query token。

    Args:
        request: 请求对象
        credentials: 认证凭据

    Returns:
        token 字符串，如果认证未启用则返回 None

    Raises:
        HTTPException: 认证失败时抛出 401 错误
    """
    return await _require_token(request, credentials, settings.write_token_list, "write")


async def verify_read_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    """
    验证读 token（用于下载文件和查询元信息）

    凭据可来自 Authorization 头 / X-Auth-Token 头 / 表单 token / query token。

    Args:
        request: 请求对象
        credentials: 认证凭据

    Returns:
        token 字符串，如果认证未启用则返回 None

    Raises:
        HTTPException: 认证失败时抛出 401 错误
    """
    return await _require_token(request, credentials, settings.read_token_list, "read")
