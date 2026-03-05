"""
文件处理服务模块
实现文件上传、下载、编码等核心功能
"""

import os
import secrets
import shutil
from pathlib import Path
from typing import Optional

from ..config import settings


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

    def save_file(self, username: str, file_content: bytes, original_filename: str) -> str:
        """
        保存上传的文件

        Args:
            username: 用户名
            file_content: 文件内容
            original_filename: 原始文件名

        Returns:
            编码后的文件名

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

        return encoded_filename

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
