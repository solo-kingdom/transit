"""
文件访问路由

- /public/{encoded}/{original} — 公开文件，无需凭据
- /protect/{token}/{original} — 受保护文件，路径内 token 即凭据
- /f/{token}/{original} — 兼容旧链接，语义同 /protect
"""

from fastapi import APIRouter, HTTPException, Path as PathParam
from fastapi.responses import FileResponse

from ..content import content_disposition, detect_content_type, is_inline
from ..services.file_service import file_service

router = APIRouter()


def _file_response(encoded_filename: str, original_filename: str) -> FileResponse:
    """按编码文件名取文件并构造响应；过期或不存在时抛 HTTP 错误"""
    file_path = file_service.get_file_path(encoded_filename)
    if file_path is None:
        raise HTTPException(status_code=404, detail="File not found")

    meta = file_service.get_meta(encoded_filename)
    if file_service.is_expired(meta):
        raise HTTPException(status_code=410, detail="File has expired")

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


@router.get("/public/{encoded_filename}/{original_filename}")
async def access_public_file(
    encoded_filename: str = PathParam(..., description="编码文件名"),
    original_filename: str = PathParam(..., description="原始文件名（仅用于美化 URL）"),
):
    """
    公开文件访问

    仅当元信息标记为未保护时可取；受保护文件不能借编码名绕过。
    """
    meta = file_service.get_meta(encoded_filename)
    if meta is None or meta.protected:
        raise HTTPException(status_code=404, detail="File not found")

    return _file_response(encoded_filename, original_filename)


@router.get("/protect/{token}/{original_filename}")
@router.get("/f/{token}/{original_filename}")
async def access_protected_file(
    token: str = PathParam(..., description="文件访问凭据"),
    original_filename: str = PathParam(..., description="原始文件名（仅用于美化 URL）"),
):
    """
    受保护文件访问（/f 为兼容别名）

    只校验路径里的凭据，不校验全局读 token——链接自足。
    """
    encoded_filename = file_service.find_by_token(token)
    if not encoded_filename:
        raise HTTPException(status_code=404, detail="File not found")

    meta = file_service.get_meta(encoded_filename)
    # 公开文件也可凭 token 访问（上传时仍会生成 token）；缺失 meta 按不存在处理
    if meta is None:
        raise HTTPException(status_code=404, detail="File not found")

    return _file_response(encoded_filename, original_filename)
