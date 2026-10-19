"""
文件路由模块：处理文件上传、下载和元信息查询
"""

from urllib.parse import quote
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path as PathParam,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import Response
from typing import Optional

from ..auth import verify_write_token, verify_read_token
from ..config import settings
from ..content import content_disposition
from ..services.file_service import file_service

router = APIRouter()


def get_download_base_url(request: Request) -> str:
    """
    获取下载的基础 URL

    优先级：
    1. 如果配置了 download_host，使用配置的 host
    2. 否则使用请求中的 host（referer host）

    Args:
        request: FastAPI 请求对象

    Returns:
        基础 URL，格式为 "http://host:port" 或 "http://host"
    """
    if settings.download_host:
        # 使用配置的 host
        return f"http://{settings.download_host}"

    # 使用请求中的 host
    # 从请求 URL 中获取 scheme、hostname 和 port
    scheme = request.url.scheme
    hostname = request.url.hostname or "localhost"
    port = request.url.port

    # 如果是标准端口（http:80, https:443），则不包含端口号
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        return f"{scheme}://{hostname}:{port}"
    else:
        return f"{scheme}://{hostname}"


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP 地址

    Args:
        request: FastAPI 请求对象

    Returns:
        客户端 IP 地址
    """
    # 检查常见的代理头
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For 可能包含多个 IP，取第一个
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    # 如果没有代理头，使用直接连接的客户端地址
    if request.client:
        return request.client.host

    return "unknown"


def _parse_expires_in(raw) -> Optional[int]:
    """
    校验有效期参数

    Args:
        raw: 客户端给的值（表单字段或 query 参数），None 表示不设置

    Returns:
        正整数秒数；未设置时返回 None

    Raises:
        HTTPException: 不是正整数时抛 400
    """
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="expires_in must be a positive integer")
    if value <= 0:
        raise HTTPException(status_code=400, detail="expires_in must be a positive integer")
    return value


def _build_upload_response(
    request: Request,
    encoded_filename: str,
    meta,
    *,
    add_hint: bool = False,
) -> dict:
    """
    构造统一的上传成功响应结构

    根据需求，上传接口只返回下载链接，避免冗余信息泄露。

    链接自带该文件专属的访问凭据，拿到链接即可取到文件，不必再带认证头。
    """
    # 访问 URL: /f/{token}/{original_filename}
    original_for_path = quote(meta.original_filename, safe="")
    download_url = f"{get_download_base_url(request)}/f/{meta.token}/{original_for_path}"

    # 最小化响应体：仅返回下载 URL；设置有效期时附带过期时间
    payload = {"download_url": download_url}
    if meta.expires_at is not None:
        payload["expires_at"] = meta.expires_at.isoformat()
    return payload


async def _upload_file_post(
    request: Request,
    file: UploadFile,
    token: Optional[str],
    expires_in: Optional[int] = None,
):
    """
    POST 上传文件的实际处理逻辑

    Args:
        request: 请求对象
        file: 上传的文件
        token: 认证 token（如果启用认证）
        expires_in: 有效期（秒）；None 表示永不过期

    Returns:
        包含完整下载 URL 的响应
    """
    try:
        # 读取文件内容
        content = await file.read()

        # 获取客户端 IP
        remote_address = get_client_ip(request)

        # 保存文件（不再区分用户名）
        encoded_filename, meta = file_service.save_file(
            file_content=content,
            original_filename=file.filename or "unnamed",
            remote_address=remote_address,
            declared_content_type=file.content_type,
            expires_in=expires_in,
        )

        # 构造统一的上传成功响应
        return _build_upload_response(request, encoded_filename, meta, add_hint=False)

    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.post("/")
async def upload_file_post(
    request: Request,
    file: UploadFile = File(..., description="要上传的文件"),
    expires_in: Optional[str] = Form(None, description="有效期（秒，正整数）；不填表示永不过期"),
    token: Optional[str] = Depends(verify_write_token),
):
    """
    使用 POST 方法上传文件（multipart/form-data 格式）

    已移除用户名逻辑，统一走单一命名空间。

    Args:
        request: 请求对象
        file: 上传的文件
        expires_in: 有效期（秒，正整数）；不填表示永不过期
        token: 认证 token（如果启用认证）

    Returns:
        包含完整下载 URL 的响应；设置有效期时含 expires_at
    """
    return await _upload_file_post(request, file, token, _parse_expires_in(expires_in))


async def _upload_file_put(
    request: Request,
    token: Optional[str],
    filename_from_path: Optional[str] = None,
    expires_in: Optional[int] = None,
):
    """
    PUT 上传文件的实际处理逻辑

    Args:
        request: 请求对象
        token: 认证 token（如果启用认证）
        filename_from_path: 从 URL 路径中提取的文件名（可选）
        expires_in: 有效期（秒）；None 表示永不过期

    Returns:
        包含完整下载 URL 的响应
    """
    try:
        # 读取原始文件内容
        content = await request.body()

        # 确定原始文件名（优先级：路径 > Content-Disposition > URL 最后一段 > 基于时间戳）
        original_filename = None

        # 1. 优先使用 URL 路径中的文件名
        if filename_from_path:
            original_filename = filename_from_path
        else:
            # 2. 尝试从 Content-Disposition 头获取文件名
            content_disposition = request.headers.get("content-disposition", "")
            if "filename=" in content_disposition:
                parts = content_disposition.split("filename=")
                if len(parts) > 1:
                    original_filename = parts[1].strip("\"'")

            # 3. 如果仍然没有文件名，尝试从 URL 最后一段推断（例如：curl -T file http://server/file.log）
            if not original_filename or original_filename == "unnamed":
                # request.url.path 形如 "/apollo.log" 或 "/logs/apollo.log"
                path = request.url.path or ""
                last_segment = path.strip("/").split("/")[-1] if path.strip("/") else ""

                # 如果最后一段看起来像带扩展名的文件（包含 "."），则作为原始文件名
                if last_segment and "." in last_segment:
                    original_filename = last_segment

            # 4. 如果仍然没有文件名，使用基于时间戳的默认文件名
            if not original_filename or original_filename == "unnamed":
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                original_filename = f"file_{timestamp}"

        # 获取客户端 IP
        remote_address = get_client_ip(request)

        # 保存文件（不再区分用户名）
        encoded_filename, meta = file_service.save_file(
            file_content=content,
            original_filename=original_filename,
            remote_address=remote_address,
            declared_content_type=request.headers.get("content-type"),
            expires_in=expires_in,
        )

        # 构造响应（PUT 方式需要在使用默认文件名时附加 hint）
        return _build_upload_response(
            request,
            encoded_filename,
            meta,
            add_hint=original_filename.startswith("file_"),
        )

    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.put("/")
async def upload_file_put_root(
    request: Request,
    expires_in: Optional[str] = Query(None, description="有效期（秒，正整数）；不填表示永不过期"),
    token: Optional[str] = Depends(verify_write_token),
):
    """
    使用 PUT 方法上传文件（原始文件内容）

    已移除用户名逻辑，统一走单一命名空间。
    当使用 `curl --upload-file` 时，可以写成：
        curl --upload-file file.log http://server/file.log

    Args:
        request: 请求对象
        expires_in: 有效期（秒，正整数）；不填表示永不过期
        token: 认证 token（如果启用认证）

    Returns:
        包含完整下载 URL 的响应；设置有效期时含 expires_at
    """
    return await _upload_file_put(request, token, expires_in=_parse_expires_in(expires_in))


@router.put("/{path:path}")
async def upload_file_put(
    request: Request,
    path: str = PathParam(..., description="文件路径（用来推断文件名，可选）"),
    expires_in: Optional[str] = Query(None, description="有效期（秒，正整数）；不填表示永不过期"),
    token: Optional[str] = Depends(verify_write_token),
):
    """
    使用 PUT 方法上传文件（原始文件内容）
    支持 curl --upload-file 命令，且移除了 username 的语义，只保留“文件名”语义。

    Args:
        request: 请求对象
        path: 请求路径（例如 apollo.log 或 logs/apollo.log）
        expires_in: 有效期（秒，正整数）；不填表示永不过期
        token: 认证 token（如果启用认证）

    Returns:
        包含完整下载 URL 的响应；设置有效期时含 expires_at
    """
    # 整个 path 只用来推断原始文件名，与存储路径无关
    # 例如:
    #   curl -T file.log http://server/file.log         -> original_filename: file.log
    #   curl -T file.log http://server/logs/file.log    -> original_filename: file.log
    #   curl -T file.log http://server/                 -> original_filename: 基于时间戳的默认名
    if path:
        filename_from_path = path.split("/")[-1]
    else:
        filename_from_path = None

    return await _upload_file_put(
        request, token, filename_from_path, _parse_expires_in(expires_in)
    )


@router.get("/{encoded_filename}/{original_filename}")
async def download_file(
    encoded_filename: str = PathParam(..., description="编码后的文件名"),
    original_filename: str = PathParam(..., description="原始文件名（仅用于美化 URL）"),
    token: Optional[str] = Depends(verify_read_token),
):
    """
    下载文件

    Args:
        encoded_filename: 编码后的文件名
        original_filename: 原始文件名（仅用于美化 URL，不参与查找）
        token: 认证 token（如果启用认证）

    Returns:
        文件内容
    """
    # 检查文件是否存在
    if not file_service.file_exists(encoded_filename):
        raise HTTPException(status_code=404, detail="File not found")

    # 读取文件内容
    content = file_service.read_file(encoded_filename)

    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    # 读取元信息以获取原始文件名
    meta = file_service.get_meta(encoded_filename)
    if file_service.is_expired(meta):
        raise HTTPException(status_code=410, detail="File has expired")

    # 确定要使用的文件名
    if meta and meta.original_filename:
        original_filename = meta.original_filename
    else:
        # 降级：使用编码后的文件名
        original_filename = encoded_filename

    # 返回文件内容
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": content_disposition(original_filename, inline=False)},
    )


@router.get("/{encoded_filename}/{original_filename}/meta")
async def get_file_meta(
    encoded_filename: str = PathParam(..., description="编码后的文件名"),
    original_filename: str = PathParam(..., description="原始文件名（仅用于美化 URL）"),
    token: Optional[str] = Depends(verify_read_token),
):
    """
    获取文件元信息

    Args:
        encoded_filename: 编码后的文件名
        token: 认证 token（如果启用认证）

    Returns:
        文件元信息（包括上传时间、原始文件名、上传者 IP 等）
    """
    # 先检查文件是否存在
    if not file_service.file_exists(encoded_filename):
        raise HTTPException(status_code=404, detail="File not found")

    # 获取元信息
    meta = file_service.get_meta(encoded_filename)

    if meta is None:
        raise HTTPException(status_code=404, detail="File metadata not found")

    if file_service.is_expired(meta):
        raise HTTPException(status_code=410, detail="File has expired")

    # 返回元信息（剔除访问凭据：持全局读 token 即可读出它，会让 per-file 凭据失去意义）
    meta_payload = meta.model_dump(mode="json")
    meta_payload.pop("token", None)

    return {
        "message": "File metadata retrieved successfully",
        "meta": meta_payload,
    }
