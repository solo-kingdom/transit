"""
配置管理模块
使用 pydantic-settings 管理应用配置
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    # 服务配置
    app_name: str = "File Transit Service"
    app_version: str = "0.1.0"

    # 数据存储路径
    data_dir: Path = Path("./data")

    # 读写端口配置（可选分离）
    write_port: int = 8000
    read_port: Optional[int] = None  # 如果为 None，则读写使用同一端口

    # 文件名编码长度
    encode_length: int = 16

    # 文件大小限制（字节），默认 100MB
    max_file_size: int = 100 * 1024 * 1024

    # 安全配置
    remove_exec_permission: bool = True

    @property
    def effective_read_port(self) -> int:
        """获取实际使用的读端口"""
        return self.read_port if self.read_port else self.write_port


# 全局配置实例
settings = Settings()
