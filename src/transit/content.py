"""
内容类型判定与响应处置

决定一个文件以什么 Content-Type 返回、是内联展示还是触发下载。
判定以文件名扩展名为准：内联与否是安全决策，不能让上传方单方面指定。
"""

import mimetypes
from typing import Optional
from urllib.parse import quote

# 视为「上传方未指定」的声明类型
UNSPECIFIED_TYPES = {"", "application/octet-stream"}

# 可以内联展示的类型前缀
INLINE_PREFIXES = ("text/", "video/", "audio/")

# 可以内联展示的完整类型
INLINE_EXACT_TYPES = {"application/pdf"}

# 可内联的图片类型中需要排除的：SVG 能内嵌脚本，内联即 XSS 入口
INLINE_EXCLUDED_TYPES = {"image/svg+xml"}

FALLBACK_TYPE = "application/octet-stream"


def detect_content_type(original_filename: str, declared: Optional[str] = None) -> str:
    """
    判定文件内容类型

    优先级：扩展名推导 > 上传请求声明的类型 > 通用二进制。
    上传方声明的类型不会覆盖扩展名推导出的结果。

    Args:
        original_filename: 原始文件名
        declared: 上传请求声明的内容类型

    Returns:
        内容类型字符串
    """
    guessed = mimetypes.guess_type(original_filename)[0]
    if guessed:
        return guessed

    if declared and declared not in UNSPECIFIED_TYPES:
        return declared

    return FALLBACK_TYPE


def is_inline(content_type: str) -> bool:
    """
    判断该内容类型是否应内联展示（而非触发下载）

    Args:
        content_type: 内容类型

    Returns:
        True 表示内联展示，False 表示作为附件下载
    """
    if content_type in INLINE_EXCLUDED_TYPES:
        return False

    if content_type.startswith(INLINE_PREFIXES):
        return True

    if content_type in INLINE_EXACT_TYPES:
        return True

    return content_type.startswith("image/")


def content_disposition(original_filename: str, inline: bool) -> str:
    """
    构造 RFC 5987 的 Content-Disposition 头值

    同时给出 ASCII 降级文件名与 UTF-8 编码的完整文件名，兼容非 ASCII 文件名。

    Args:
        original_filename: 原始文件名
        inline: 是否内联展示

    Returns:
        Content-Disposition 头值
    """
    disposition = "inline" if inline else "attachment"
    quoted = quote(original_filename, safe="")
    ascii_filename = original_filename.encode("ascii", "replace").decode("ascii")

    return f"{disposition}; filename=\"{ascii_filename}\"; filename*=UTF-8''{quoted}"
