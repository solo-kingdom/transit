"""
配置管理模块
使用 pydantic-settings 管理应用配置
"""

from pathlib import Path
from typing import Optional, List

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
    data_dir: Path = Path("/app/transit/data")

    # 服务端口（单一端口，读写分离由反向代理控制）
    port: int = 8000

    # 文件大小限制（字节），默认 5GB
    max_file_size: int = 5 * 1024 * 1024 * 1024

    # 安全配置
    remove_exec_permission: bool = True

    # 下载 Host 配置
    # 如果为空，则使用请求中的 host（referer host）
    # 如果配置了值，则使用配置的 host
    download_host: str = ""

    # 认证配置
    # 是否启用认证
    auth_enabled: bool = False

    # 读 token 列表（多个 token 用逗号分隔）
    # 用于下载文件和查询元信息
    read_tokens: str = ""

    # 写 token 列表（多个 token 用逗号分隔）
    # 用于上传文件
    write_tokens: str = ""

    @property
    def read_token_list(self) -> List[str]:
        """获取读 token 列表"""
        if not self.read_tokens:
            return []
        return [token.strip() for token in self.read_tokens.split(",") if token.strip()]

    @property
    def write_token_list(self) -> List[str]:
        """获取写 token 列表"""
        if not self.write_tokens:
            return []
        return [token.strip() for token in self.write_tokens.split(",") if token.strip()]


# 全局配置实例
settings = Settings()
