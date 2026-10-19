"""
文件处理服务模块
实现文件上传、下载、编码等核心功能
"""

import json
import os
import secrets
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import settings
from ..content import detect_content_type
from ..models.meta import FileMeta


class FileService:
    """文件服务类"""

    def __init__(self):
        self.data_dir = settings.data_dir
        self.max_file_size = settings.max_file_size
        self.remove_exec_permission = settings.remove_exec_permission

        # 访问凭据 -> 编码文件名 的反查索引
        # 访问路径是热路径（一次播放会发多次分段请求），逐请求扫元信息文件不可接受；
        # 这里只缓存本进程写入的内容，首次访问时构建，进程重启后重建
        self._token_index: Optional[dict[str, str]] = None

        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def generate_encoded_filename(self, original_filename: str) -> str:
        """
        生成随机编码的文件名（使用 UUID）

        Args:
            original_filename: 原始文件名

        Returns:
            编码后的文件名（保留原始扩展名）
        """
        # 使用 UUID 生成唯一标识符
        unique_id = str(uuid.uuid4())

        # 获取文件扩展名
        ext = Path(original_filename).suffix

        # 组合成新文件名
        encoded_filename = f"{unique_id}{ext}"

        return encoded_filename

    def generate_token(self) -> str:
        """
        生成文件的访问凭据

        128 位随机量，不做唯一性检查——碰撞概率可忽略，
        而为它逐次扫描全部元信息文件得不偿失。

        Returns:
            访问凭据字符串
        """
        return secrets.token_urlsafe(16)

    def _build_token_index(self) -> dict[str, str]:
        """扫描元信息文件构建访问凭据索引"""
        index: dict[str, str] = {}

        for meta_path in self.data_dir.glob(".meta.*.json"):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            token = data.get("token")
            encoded_filename = data.get("encoded_filename")
            if token and encoded_filename:
                index[token] = encoded_filename

        return index

    def find_by_token(self, token: str) -> Optional[str]:
        """
        按访问凭据反查编码文件名

        Args:
            token: 访问凭据

        Returns:
            编码文件名，没有对应文件时返回 None
        """
        if not token:
            return None

        if self._token_index is None:
            self._token_index = self._build_token_index()

        return self._token_index.get(token)

    def get_file_path(self, encoded_filename: str) -> Path:
        """
        获取文件的完整路径（不再区分用户名）

        Args:
            encoded_filename: 编码后的文件名

        Returns:
            文件完整路径
        """
        return self.data_dir / encoded_filename

    def get_meta_path(self, encoded_filename: str) -> Path:
        """
        获取元信息文件的完整路径（不再区分用户名）

        Args:
            encoded_filename: 编码后的文件名

        Returns:
            元信息文件完整路径
        """
        # 元信息文件名格式：.meta.{encoded_filename}.json
        meta_filename = f".meta.{encoded_filename}.json"
        return self.data_dir / meta_filename

    def save_meta(
        self,
        encoded_filename: str,
        original_filename: str,
        file_size: int,
        remote_address: str,
        token: str,
        content_type: str,
    ) -> FileMeta:
        """
        保存文件元信息

        Args:
            encoded_filename: 编码后的文件名
            original_filename: 原始文件名
            file_size: 文件大小
            remote_address: 上传者 IP 地址
            token: 访问凭据
            content_type: 内容类型

        Returns:
            文件元信息对象
        """
        meta = FileMeta(
            encoded_filename=encoded_filename,
            original_filename=original_filename,
            upload_time=datetime.now(),
            remote_address=remote_address,
            file_size=file_size,
            token=token,
            content_type=content_type,
        )

        meta_path = self.get_meta_path(encoded_filename)

        # 保存为 JSON 文件
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)

        return meta

    def get_meta(self, encoded_filename: str) -> Optional[FileMeta]:
        """
        读取文件元信息

        Args:
            encoded_filename: 编码后的文件名

        Returns:
            文件元信息对象，如果不存在则返回 None
        """
        meta_path = self.get_meta_path(encoded_filename)

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
        file_content: bytes,
        original_filename: str,
        remote_address: str,
        declared_content_type: Optional[str] = None,
    ) -> tuple[str, FileMeta]:
        """
        保存上传的文件

        Args:
            file_content: 文件内容
            original_filename: 原始文件名
            remote_address: 上传者 IP 地址
            declared_content_type: 上传请求声明的内容类型（仅在扩展名推导不出时采用）

        Returns:
            元组：(编码后的文件名, 文件元信息)

        Raises:
            ValueError: 文件大小超过限制
        """
        # 检查文件大小
        if len(file_content) > self.max_file_size:
            raise ValueError(f"File size exceeds maximum limit of {self.max_file_size} bytes")

        # 生成编码文件名，并确保唯一（UUID 冲突概率极低，这里只是防御性检查）
        encoded_filename = self.generate_encoded_filename(original_filename)
        file_path = self.get_file_path(encoded_filename)

        while file_path.exists():
            encoded_filename = self.generate_encoded_filename(original_filename)
            file_path = self.get_file_path(encoded_filename)

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_content)

        # 移除执行权限（安全措施）
        if self.remove_exec_permission:
            self._remove_exec_permission(file_path)

        # 生成访问凭据与内容类型
        token = self.generate_token()
        content_type = detect_content_type(original_filename, declared_content_type)

        # 保存元信息
        meta = self.save_meta(
            encoded_filename=encoded_filename,
            original_filename=original_filename,
            file_size=len(file_content),
            remote_address=remote_address,
            token=token,
            content_type=content_type,
        )

        # 写入索引，使新文件立刻可被反查到
        if self._token_index is not None:
            self._token_index[token] = encoded_filename

        return encoded_filename, meta

    def read_file(self, encoded_filename: str) -> Optional[bytes]:
        """
        读取文件内容

        Args:
            encoded_filename: 编码后的文件名

        Returns:
            文件内容，如果文件不存在则返回 None
        """
        file_path = self.get_file_path(encoded_filename)

        if not file_path.exists():
            return None

        with open(file_path, "rb") as f:
            return f.read()

    def file_exists(self, encoded_filename: str) -> bool:
        """
        检查文件是否存在

        Args:
            encoded_filename: 编码后的文件名

        Returns:
            文件是否存在
        """
        file_path = self.get_file_path(encoded_filename)
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
