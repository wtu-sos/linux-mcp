"""Configuration module for Linux SSH MCP server."""

import json
import os
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ServerConfig(BaseModel):
    """单个服务器的 SSH 连接和安全层配置。"""

    name: str = Field(description="服务器名称，用于工具调用时指定目标")
    host: str = Field(default="", description="远程主机地址")
    port: int = Field(default=22, description="SSH 端口")
    username: str = Field(default="", description="SSH 用户名")
    password: Optional[str] = Field(default=None, description="SSH 密码")
    key_file: Optional[str] = Field(default=None, description="SSH 私钥路径")
    timeout: int = Field(default=30, description="连接超时（秒）")
    command_timeout: int = Field(default=60, description="命令执行超时（秒）")

    # Output limits
    max_output_size: int = Field(
        default=1024 * 1024, description="命令输出最大大小（字节），默认 1MB"
    )
    max_read_size: int = Field(
        default=10 * 1024 * 1024, description="文件读取最大大小（字节），默认 10MB"
    )
    max_upload_size: int = Field(
        default=10 * 1024 * 1024, description="文件上传最大大小（字节），默认 10MB"
    )

    # Safety layer
    trash_dir: str = Field(
        default="~/.linux_mcp_trash", description="回收站目录路径"
    )
    audit_log_path: str = Field(
        default="~/.linux_mcp_audit.log", description="审计日志文件路径"
    )
    max_trash_size: int = Field(
        default=100 * 1024 * 1024, description="回收站警告阈值（字节），默认 100MB"
    )
    max_audit_size: int = Field(
        default=10 * 1024 * 1024, description="审计日志轮转大小（字节），默认 10MB"
    )

    # Process listing
    max_processes: int = Field(
        default=200, description="进程列表最大返回数量"
    )

    @model_validator(mode="after")
    def validate_required_fields(self) -> "ServerConfig":
        """Validate that required fields are present."""
        if not self.host:
            raise ValueError(f"服务器 '{self.name}': host 是必填项")
        if not self.username:
            raise ValueError(f"服务器 '{self.name}': username 是必填项")
        if not self.password and not self.key_file:
            raise ValueError(
                f"服务器 '{self.name}': 必须提供 password 或 key_file 中的至少一种认证方式"
            )
        return self

    def expand_remote_path(self, path: str) -> str:
        """Expand ~ in a remote path. Uses /home/{username} instead of local home."""
        if path.startswith("~"):
            remote_home = f"/home/{self.username}"
            path = remote_home + path[1:]
        return os.path.expandvars(path)

    def expand_local_path(self, path: str) -> str:
        """Expand ~ and env vars in a local path (e.g. key_file on Windows)."""
        expanded = os.path.expanduser(path)
        expanded = os.path.expandvars(expanded)
        return expanded

    @property
    def trash_dir_expanded(self) -> str:
        return self.expand_remote_path(self.trash_dir)

    @property
    def audit_log_path_expanded(self) -> str:
        return self.expand_remote_path(self.audit_log_path)

    @property
    def key_file_expanded(self) -> Optional[str]:
        if self.key_file:
            return self.expand_local_path(self.key_file)
        return None


class AppConfig(BaseModel):
    """应用顶层配置，包含多台服务器配置。"""

    servers: list[ServerConfig]

    @model_validator(mode="after")
    def validate_names_unique(self) -> "AppConfig":
        """验证服务器名称唯一性。"""
        names = [s.name for s in self.servers]
        if len(names) != len(set(names)):
            seen = set()
            for n in names:
                if n in seen:
                    raise ValueError(f"服务器名称重复: '{n}'")
                seen.add(n)
        if not self.servers:
            raise ValueError("至少需要配置一台服务器")
        return self

    @property
    def is_single_server(self) -> bool:
        return len(self.servers) == 1

    @property
    def default_name(self) -> str:
        return self.servers[0].name

    def get_server(self, name: str) -> ServerConfig:
        for s in self.servers:
            if s.name == name:
                return s
        raise ValueError(f"服务器 '{name}' 不存在")

    @property
    def server_names(self) -> list[str]:
        return [s.name for s in self.servers]


def _load_json_file(config_path: str) -> dict:
    """从 JSON 文件加载原始配置。"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _merge_with_defaults(server: dict, defaults: dict) -> dict:
    """合并 defaults 和 server 条目，server 覆盖 defaults。"""
    merged = {**defaults, **server}
    return merged


def _wrap_legacy_format(raw: dict) -> dict:
    """将旧格式（扁平）包装为新格式。"""
    if "host" in raw and "servers" not in raw:
        return {"servers": [{"name": "default", **raw}]}
    return raw


def load_config(config_path: str) -> AppConfig:
    """从 JSON 配置文件加载配置。

    支持新格式（servers 数组 + defaults）和旧格式（扁平）自动兼容。
    """
    raw = _load_json_file(config_path)

    # 旧格式兼容
    raw = _wrap_legacy_format(raw)

    # 提取 defaults
    defaults = raw.pop("defaults", {})

    # 合并并构建 ServerConfig
    servers = []
    for s in raw["servers"]:
        merged = _merge_with_defaults(s, defaults)
        servers.append(ServerConfig(**merged))

    return AppConfig(servers=servers)
