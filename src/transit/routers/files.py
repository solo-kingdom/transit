"""
文件路由模块
处理文件上传和下载请求
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Path as PathParam, Request
from fastapi.responses import Response

from ..services.file_service import file_service

# 创建路由器
router = APIRouter()


@router.post("/{username}")
async def upload_file_post(
    username: str = PathParam(..., description="用户名"),
    file: UploadFile = File(..., description="要上传的文件"),
):
    """
    使用 POST 方法上传文件（multipart/form-data 格式）

    Args:
        username: 用户名
        file: 上传的文件

    Returns:
        包含下载路径的响应
    """
    try:
        # 读取文件内容
        content = await file.read()

        # 保存文件
        encoded_filename = file_service.save_file(
            username=username, file_content=content, original_filename=file.filename or "unnamed"
        )

        # 构造下载路径
        download_path = f"/{username}/{encoded_filename}"

        return {
            "message": "File uploaded successfully",
            "download_path": download_path,
            "filename": encoded_filename,
        }

    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.put("/{username}")
async def upload_file_put(
    request: Request,
    username: str = PathParam(..., description="用户名"),
):
    """
    使用 PUT 方法上传文件（原始文件内容）
    支持 curl --upload-file 命令

    Args:
        request: 请求对象
        username: 用户名

    Returns:
        包含下载路径的响应
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

        # 保存文件
        encoded_filename = file_service.save_file(
            username=username, file_content=content, original_filename=original_filename
        )

        # 构造下载路径
        download_path = f"/{username}/{encoded_filename}"

        return {
            "message": "File uploaded successfully",
            "download_path": download_path,
            "filename": encoded_filename,
        }

    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/{username}/{encoded_filename}")
async def download_file(
    username: str = PathParam(..., description="用户名"),
    encoded_filename: str = PathParam(..., description="编码后的文件名"),
):
    """
    下载文件

    Args:
        username: 用户名
        encoded_filename: 编码后的文件名

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
