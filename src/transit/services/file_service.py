"""
文件处理服务模块
实现文件上传、下载、编码等核心功能
"""

import json
import os
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import settings
from ..models.meta import FileMeta


class FileService:
    """文件服务类"""

    def __init__(self):
        self.data_dir = settings.data_dir
        self.encode_length = settings.encode_length
        self.max_file_size = settings.max_file_size
        self.remove_exec_permission = settings.remove_exec_permission

        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def generate_encoded_filename(self, original_filename: str) -> str:
        """
        生成随机编码的文件名

        Args:
            original_filename: 原始文件名

        Returns:
            编码后的文件名（保留原始扩展名）
        """
        # 生成随机字符串
        random_str = secrets.token_urlsafe(self.encode_length)

        # 获取文件扩展名
        ext = Path(original_filename).suffix

        # 组合成新文件名
        encoded_filename = f"{random_str}{ext}"

        return encoded_filename

    def get_user_dir(self, username: str) -> Path:
        """
        获取用户目录路径

        Args:
            username: 用户名

        Returns:
            用户目录路径
        """
        user_dir = self.data_dir / username
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def get_file_path(self, username: str, encoded_filename: str) -> Path:
        """
        获取文件的完整路径

        Args:
            username: 用户名
            encoded_filename: 编码后的文件名

        Returns:
            文件完整路径
        """
        return self.get_user_dir(username) / encoded_filename

    def get_meta_path(self, username: str, encoded_filename: str) -> Path:
        """
        获取元信息文件的完整路径

        Args:
            username: 用户名
            encoded_filename: 编码后的文件名

        Returns:
            元信息文件完整路径
        """
        user_dir = self.get_user_dir(username)
        # 元信息文件名格式：.meta.{encoded_filename}.json
        meta_filename = f".meta.{encoded_filename}.json"
        return user_dir / meta_filename

    def save_meta(
        self,
        username: str,
        encoded_filename: str,
        original_filename: str,
        file_size: int,
        remote_address: str,
    ) -> FileMeta:
        """
        保存文件元信息

        Args:
            username: 用户名
            encoded_filename: 编码后的文件名
            original_filename: 原始文件名
            file_size: 文件大小
            remote_address: 上传者 IP 地址

        Returns:
            文件元信息对象
        """
        meta = FileMeta(
            encoded_filename=encoded_filename,
            original_filename=original_filename,
            upload_time=datetime.now(),
            remote_address=remote_address,
            file_size=file_size,
            username=username,
            file_path=f"{username}/{encoded_filename}",
        )

        meta_path = self.get_meta_path(username, encoded_filename)

        # 保存为 JSON 文件
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)

        return meta

    def get_meta(self, username: str, encoded_filename: str) -> Optional[FileMeta]:
        """
        读取文件元信息

        Args:
            username: 用户名
            encoded_filename: 编码后的文件名

        Returns:
            文件元信息对象，如果不存在则返回 None
        """
        meta_path = self.get_meta_path(username, encoded_filename)

        if not meta_path.exists():
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 将字符串时间转换回 datetime
                if isinstance(data.get("upload_time"), str):
                    data["upload_time"] = datetime.fromisoformat(data["upload_time"])
                return FileMeta(**data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def save_file(
        self,
        username: str,
        file_content: bytes,
        original_filename: str,
        remote_address: str,
    ) -> tuple[str, FileMeta]:
        """
        保存上传的文件

        Args:
            username: 用户名
            file_content: 文件内容
            original_filename: 原始文件名
            remote_address: 上传者 IP 地址

        Returns:
            元组：(编码后的文件名, 文件元信息)

        Raises:
            ValueError: 文件大小超过限制
        """
        # 检查文件大小
        if len(file_content) > self.max_file_size:
            raise ValueError(f"File size exceeds maximum limit of {self.max_file_size} bytes")

        # 生成编码文件名
        encoded_filename = self.generate_encoded_filename(original_filename)

        # 获取文件路径
        file_path = self.get_file_path(username, encoded_filename)

        # 确保文件名唯一（虽然概率极低，但还是要检查）
        while file_path.exists():
            encoded_filename = self.generate_encoded_filename(original_filename)
            file_path = self.get_file_path(username, encoded_filename)

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_content)

        # 移除执行权限（安全措施）
        if self.remove_exec_permission:
            self._remove_exec_permission(file_path)

        # 保存元信息
        meta = self.save_meta(
            username=username,
            encoded_filename=encoded_filename,
            original_filename=original_filename,
            file_size=len(file_content),
            remote_address=remote_address,
        )

        return encoded_filename, meta

    def read_file(self, username: str, encoded_filename: str) -> Optional[bytes]:
        """
        读取文件内容

        Args:
            username: 用户名
            encoded_filename: 编码后的文件名

        Returns:
            文件内容，如果文件不存在则返回 None
        """
        file_path = self.get_file_path(username, encoded_filename)

        if not file_path.exists():
            return None

        with open(file_path, "rb") as f:
            return f.read()

    def file_exists(self, username: str, encoded_filename: str) -> bool:
        """
        检查文件是否存在

        Args:
            username: 用户名
            encoded_filename: 编码后的文件名

        Returns:
            文件是否存在
        """
        file_path = self.get_file_path(username, encoded_filename)
        return file_path.exists() and file_path.is_file()

    def _remove_exec_permission(self, file_path: Path) -> None:
        """
        移除文件的执行权限

        Args:
            file_path: 文件路径
        """
        # 获取当前权限
        current_mode = file_path.stat().st_mode

        # 移除所有执行权限（用户、组、其他）
        new_mode = current_mode & ~0o111

        # 设置新权限
        file_path.chmod(new_mode)


# 全局文件服务实例
file_service = FileService()
