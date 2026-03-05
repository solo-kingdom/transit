"""
文件路由模块
处理文件上传和下载请求
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Path as PathParam, Request, Depends
from fastapi.responses import Response
from typing import Optional

from ..auth import verify_write_token, verify_read_token
from ..config import settings
from ..services.file_service import file_service

# 创建路由器
router = APIRouter()


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


@router.post("/{username}")
async def upload_file_post(
    request: Request,
    username: str = PathParam(..., description="用户名"),
    file: UploadFile = File(..., description="要上传的文件"),
    token: Optional[str] = Depends(verify_write_token),
):
    """
    使用 POST 方法上传文件（multipart/form-data 格式）

    Args:
        request: 请求对象
        username: 用户名
        file: 上传的文件
        token: 认证 token（如果启用认证）

    Returns:
        包含完整下载 URL 的响应
    """
    try:
        # 读取文件内容
        content = await file.read()

        # 获取客户端 IP
        remote_address = get_client_ip(request)

        # 保存文件
        encoded_filename, meta = file_service.save_file(
            username=username,
            file_content=content,
            original_filename=file.filename or "unnamed",
            remote_address=remote_address,
        )

        # 构造下载 URL（完整 URL）
        download_url = f"{settings.download_base_url}/{username}/{encoded_filename}"

        return {
            "message": "File uploaded successfully",
            "download_url": download_url,
            "download_path": f"/{username}/{encoded_filename}",
            "filename": encoded_filename,
            "meta": meta.model_dump(mode="json"),
        }

    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.put("/{username}")
async def upload_file_put(
    request: Request,
    username: str = PathParam(..., description="用户名"),
    token: Optional[str] = Depends(verify_write_token),
):
    """
    使用 PUT 方法上传文件（原始文件内容）
    支持 curl --upload-file 命令

    Args:
        request: 请求对象
        username: 用户名
        token: 认证 token（如果启用认证）

    Returns:
        包含完整下载 URL 的响应
    """
    try:
        # 读取原始文件内容
        content = await request.body()

        # 从请求头获取文件名（如果有）
        content_disposition = request.headers.get("content-disposition", "")
        original_filename = "unnamed"

        # 尝试从 Content-Disposition 提取文件名
        if "filename=" in content_disposition:
            parts = content_disposition.split("filename=")
            if len(parts) > 1:
                original_filename = parts[1].strip("\"'")

        # 获取客户端 IP
        remote_address = get_client_ip(request)

        # 保存文件
        encoded_filename, meta = file_service.save_file(
            username=username,
            file_content=content,
            original_filename=original_filename,
            remote_address=remote_address,
        )

        # 构造下载 URL（完整 URL）
        download_url = f"{settings.download_base_url}/{username}/{encoded_filename}"

        return {
            "message": "File uploaded successfully",
            "download_url": download_url,
            "download_path": f"/{username}/{encoded_filename}",
            "filename": encoded_filename,
            "meta": meta.model_dump(mode="json"),
        }

    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/{username}/{encoded_filename}")
async def download_file(
    username: str = PathParam(..., description="用户名"),
    encoded_filename: str = PathParam(..., description="编码后的文件名"),
    token: Optional[str] = Depends(verify_read_token),
):
    """
    下载文件

    Args:
        username: 用户名
        encoded_filename: 编码后的文件名
        token: 认证 token（如果启用认证）

    Returns:
        文件内容
    """
    # 检查文件是否存在
    if not file_service.file_exists(username, encoded_filename):
        raise HTTPException(status_code=404, detail="File not found")

    # 读取文件内容
    content = file_service.read_file(username, encoded_filename)

    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    # 返回文件内容
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={encoded_filename}"},
    )


@router.get("/{username}/{encoded_filename}/meta")
async def get_file_meta(
    username: str = PathParam(..., description="用户名"),
    encoded_filename: str = PathParam(..., description="编码后的文件名"),
    token: Optional[str] = Depends(verify_read_token),
):
    """
    获取文件元信息

    Args:
        username: 用户名
        encoded_filename: 编码后的文件名
        token: 认证 token（如果启用认证）

    Returns:
        文件元信息（包括上传时间、原始文件名、上传者 IP 等）
    """
    # 先检查文件是否存在
    if not file_service.file_exists(username, encoded_filename):
        raise HTTPException(status_code=404, detail="File not found")

    # 获取元信息
    meta = file_service.get_meta(username, encoded_filename)

    if meta is None:
        raise HTTPException(status_code=404, detail="File metadata not found")

    # 返回元信息
    return {
        "message": "File metadata retrieved successfully",
        "meta": meta.model_dump(mode="json"),
    }
