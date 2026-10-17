"""
文件访问路由

按文件专属的访问凭据取文件：链接本身就是访问方式，不依赖全局读 token。
"""

from fastapi import APIRouter, HTTPException, Path as PathParam
from fastapi.responses import FileResponse

from ..content import content_disposition, detect_content_type, is_inline
from ..services.file_service import file_service

router = APIRouter()


@router.get("/f/{token}/{original_filename}")
async def access_file(
    token: str = PathParam(..., description="文件访问凭据"),
    original_filename: str = PathParam(..., description="原始文件名（仅用于美化 URL）"),
):
    """
    按访问凭据取文件

    只校验路径里的凭据，不校验全局读 token——否则服务启用认证时，
    不带认证头的链接会 401，链接就不自足了。

    返回处置按内容类型决定：文本、图片（矢量图除外）、音视频与 PDF 内联展示，
    其余触发下载。分段请求由 FileResponse 承担，音视频可跳转播放。

    Args:
        token: 文件访问凭据
        original_filename: 原始文件名（仅用于美化 URL，不参与查找）

    Returns:
        文件内容
    """
    encoded_filename = file_service.find_by_token(token)
    if not encoded_filename:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = file_service.get_file_path(encoded_filename)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    meta = file_service.get_meta(encoded_filename)
    filename = meta.original_filename if meta and meta.original_filename else original_filename
    content_type = (
        meta.content_type if meta and meta.content_type else detect_content_type(filename)
    )

    return FileResponse(
        file_path,
        media_type=content_type,
        headers={
            "Content-Disposition": content_disposition(filename, inline=is_inline(content_type)),
            "X-Content-Type-Options": "nosniff",
        },
    )
