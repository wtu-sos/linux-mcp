"""Configuration module for Linux SSH MCP server."""

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class Config(BaseModel):
    """Configuration for SSH connection and safety layer."""

    # SSH connection
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
    def validate_required_fields(self) -> "Config":
        """Validate that required fields are present."""
        if not self.host:
            raise ValueError("host 是必填项，请通过配置文件或 SSH_HOST 环境变量设置")
        if not self.username:
            raise ValueError("username 是必填项，请通过配置文件或 SSH_USER 环境变量设置")
        if not self.password and not self.key_file:
            raise ValueError("必须提供 password 或 key_file 中的至少一种认证方式")
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


def load_config_from_file(config_path: str) -> dict:
    """从 JSON 文件加载配置。"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config_from_env() -> dict:
    """从环境变量加载配置。"""
    env_mapping = {
        "host": "SSH_HOST",
        "port": "SSH_PORT",
        "username": "SSH_USER",
        "password": "SSH_PASSWORD",
        "key_file": "SSH_KEY_FILE",
        "timeout": "SSH_TIMEOUT",
        "command_timeout": "SSH_COMMAND_TIMEOUT",
        "max_output_size": "MCP_MAX_OUTPUT_SIZE",
        "max_read_size": "MCP_MAX_READ_SIZE",
        "max_upload_size": "MCP_MAX_UPLOAD_SIZE",
        "trash_dir": "MCP_TRASH_DIR",
        "audit_log_path": "MCP_AUDIT_LOG",
        "max_trash_size": "MCP_MAX_TRASH_SIZE",
        "max_audit_size": "MCP_MAX_AUDIT_SIZE",
        "max_processes": "MCP_MAX_PROCESSES",
    }

    env_config = {}
    for key, env_var in env_mapping.items():
        value = os.environ.get(env_var)
        if value is not None:
            # Convert numeric types
            if key in (
                "port",
                "timeout",
                "command_timeout",
                "max_output_size",
                "max_read_size",
                "max_upload_size",
                "max_trash_size",
                "max_audit_size",
                "max_processes",
            ):
                try:
                    env_config[key] = int(value)
                except ValueError:
                    pass
            else:
                env_config[key] = value

    return env_config


def create_config(config_path: Optional[str] = None) -> Config:
    """创建配置对象。

    优先级：环境变量 > 配置文件 > 默认值
    """
    config_data = {}

    # 1. 从配置文件加载
    if config_path:
        config_data.update(load_config_from_file(config_path))

    # 2. 环境变量覆盖
    config_data.update(load_config_from_env())

    # 3. 创建并验证
    return Config(**config_data)
