"""
文件处理服务模块
实现文件上传、下载、编码等核心功能
"""

import json
import os
import secrets
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..config import settings
from ..content import detect_content_type
from ..models.meta import FileMeta

# 元信息文件名形态：.meta.{编码文件名}.json，与文件同放在数据目录下
META_PREFIX = ".meta."
META_SUFFIX = ".json"


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

        for meta_path in self.data_dir.glob(f"{META_PREFIX}*{META_SUFFIX}"):
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

    def _safe_encoded_name(self, encoded_filename: str) -> Optional[str]:
        """
        校验编码文件名

        必须是单个普通路径段，且不是元信息文件本身——元信息与文件同目录，且带
        per-file 访问凭据，能按名取到它就等于拿到了该文件的凭据。

        Args:
            encoded_filename: 客户端给出的编码文件名

        Returns:
            通过校验的编码文件名；不合法时返回 None
        """
        if not encoded_filename or encoded_filename != Path(encoded_filename).name:
            return None

        if encoded_filename in {".", ".."}:
            return None

        if encoded_filename.startswith(META_PREFIX):
            return None

        return encoded_filename

    def get_file_path(self, encoded_filename: str) -> Optional[Path]:
        """
        把编码文件名解析为数据目录内的普通文件

        先拼接再 `resolve()`，然后用「是否仍在数据目录内」判定——`resolve()` 会展开
        符号链接与 `..`，绝对路径在拼接时会丢弃左边的根，三种逃逸方式因此收敛成同一句
        判定，不需要另外枚举禁止模式（与页面资源侧同一套做法）。

        Args:
            encoded_filename: 编码后的文件名

        Returns:
            文件路径；编码名不合法、解析结果越出数据目录、或不是普通文件时返回 None
        """
        name = self._safe_encoded_name(encoded_filename)
        if name is None:
            return None

        root = self.data_dir.resolve()
        try:
            candidate = (root / name).resolve()
        except (OSError, RuntimeError):
            return None

        if not candidate.is_relative_to(root):
            return None

        if not candidate.is_file():
            return None

        return candidate

    def get_meta_path(self, encoded_filename: str) -> Path:
        """
        获取元信息文件的完整路径（不再区分用户名）

        Args:
            encoded_filename: 编码后的文件名

        Returns:
            元信息文件完整路径
        """
        return self.data_dir / f"{META_PREFIX}{encoded_filename}{META_SUFFIX}"

    def save_meta(
        self,
        encoded_filename: str,
        original_filename: str,
        file_size: int,
        remote_address: str,
        token: str,
        content_type: str,
        expires_in: Optional[int] = None,
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
            expires_in: 有效期（秒）；None 表示永不过期

        Returns:
            文件元信息对象
        """
        now = datetime.now()
        meta = FileMeta(
            encoded_filename=encoded_filename,
            original_filename=original_filename,
            upload_time=now,
            remote_address=remote_address,
            file_size=file_size,
            token=token,
            content_type=content_type,
            expires_at=now + timedelta(seconds=expires_in) if expires_in else None,
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
        name = self._safe_encoded_name(encoded_filename)
        if name is None:
            return None

        meta_path = self.get_meta_path(name)

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

    def is_expired(self, meta: Optional[FileMeta]) -> bool:
        """
        判断元信息是否已过期

        没有元信息、或元信息里没有 expires_at 时都视为未过期：
        前者交给调用方按「文件不存在」处理，后者兼容升级前写入的旧文件。

        Args:
            meta: 文件元信息，可以为 None

        Returns:
            是否已过期
        """
        if meta is None or meta.expires_at is None:
            return False

        now = datetime.now(tz=meta.expires_at.tzinfo)
        return now >= meta.expires_at

    def save_file(
        self,
        file_content: bytes,
        original_filename: str,
        remote_address: str,
        declared_content_type: Optional[str] = None,
        expires_in: Optional[int] = None,
    ) -> tuple[str, FileMeta]:
        """
        保存上传的文件

        Args:
            file_content: 文件内容
            original_filename: 原始文件名
            remote_address: 上传者 IP 地址
            declared_content_type: 上传请求声明的内容类型（仅在扩展名推导不出时采用）
            expires_in: 有效期（秒）；None 表示永不过期

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
        file_path = self.data_dir / encoded_filename

        while file_path.exists():
            encoded_filename = self.generate_encoded_filename(original_filename)
            file_path = self.data_dir / encoded_filename

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
            expires_in=expires_in,
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

        if file_path is None:
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
        return self.get_file_path(encoded_filename) is not None

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
