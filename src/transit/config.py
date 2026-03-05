"""
配置管理模块
使用 pydantic-settings 管理应用配置
"""

import socket
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_local_ip() -> str:
    """
    获取本机 IP 地址

    Returns:
        本机 IP 地址，如果无法获取则返回 127.0.0.1
    """
    try:
        # 创建一个 UDP socket 连接到外部地址（不会真正发送数据）
        # 这样可以获取本机用于访问外网的路由 IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # 连接到 Google DNS（不需要真正连接）
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            return local_ip
    except Exception:
        # 如果获取失败，返回 localhost
        return "127.0.0.1"


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

    # 下载 Host 配置
    # 如果为 None，则自动获取本机 IP
    download_host: Optional[str] = None

    @property
    def effective_read_port(self) -> int:
        """获取实际使用的读端口"""
        return self.read_port if self.read_port else self.write_port

    @property
    def effective_download_host(self) -> str:
        """获取实际使用的下载 host"""
        if self.download_host:
            return self.download_host
        # 自动获取本机 IP
        return get_local_ip()

    @property
    def download_base_url(self) -> str:
        """获取下载的基础 URL"""
        host = self.effective_download_host
        port = self.effective_read_port

        # 如果是默认端口（80 或 443），则不显示端口号
        if port in (80, 443):
            return f"http://{host}"
        else:
            return f"http://{host}:{port}"


# 全局配置实例
settings = Settings()
