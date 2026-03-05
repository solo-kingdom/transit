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

    # （已移除 username 和按用户名分目录的概念）
