"""
文件元信息数据模型
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FileMeta(BaseModel):
    """文件元信息"""

    # 编码后的文件名
    encoded_filename: str

    # 原始文件名
    original_filename: str

    # 上传时间
    upload_time: datetime

    # 上传者的 IP 地址
    remote_address: str

    # 文件大小（字节）
    file_size: int

    # 访问凭据：受保护文件用它组成 /protect/{token}/... 链接
    # 本次变更前写入的元信息文件没有这个字段，默认空串
    token: str = ""

    # 是否走受保护命名空间；缺省 True（兼容旧文件，等同原 /f/ 语义）
    protected: bool = True

    # 上传时判定的内容类型，决定内联展示还是下载
    # 本次变更前写入的元信息文件没有这个字段，默认空串
    content_type: str = ""

    # 文件过期时间；为空表示永不过期
    # 本次变更前写入的元信息文件没有这个字段，默认 None（即不过期）
    expires_at: Optional[datetime] = None

    # （已移除 username 和按用户名分目录的概念）
