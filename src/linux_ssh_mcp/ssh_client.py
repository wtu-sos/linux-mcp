"""SSH client module using asyncssh for remote Linux operations."""

import asyncio
import logging
from typing import Any, Optional

import asyncssh

from .config import Config

logger = logging.getLogger(__name__)


class SSHClient:
    """Async SSH client for remote Linux operations."""

    def __init__(self, config: Config):
        self._config = config
        self._conn: Optional[asyncssh.SSHClientConnection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """建立 SSH 连接。"""
        if self._conn and not self._conn.is_closed():
            return

        connect_kwargs: dict[str, Any] = {
            "host": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
            "connect_timeout": self._config.timeout,
            "known_hosts": None,  # 跳过 known_hosts 检查
        }

        if self._config.key_file_expanded:
            connect_kwargs["client_keys"] = [self._config.key_file_expanded]
        elif self._config.password:
            connect_kwargs["password"] = self._config.password

        logger.info("正在连接到 %s@%s:%d", self._config.username, self._config.host, self._config.port)
        self._conn = await asyncssh.connect(**connect_kwargs)
        logger.info("SSH 连接已建立")

    async def disconnect(self) -> None:
        """关闭 SSH 连接。"""
        if self._conn and not self._conn.is_closed():
            self._conn.close()
            await self._conn.wait_closed()
            logger.info("SSH 连接已关闭")
        self._conn = None

    async def ensure_connected(self) -> None:
        """确保连接活跃，必要时自动重连。"""
        async with self._lock:
            if self._conn is None or self._conn.is_closed():
                await self.connect()

    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        env: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """执行 Shell 命令。

        Returns:
            dict with keys: stdout, stderr, exit_code
        """
        await self.ensure_connected()

        cmd_timeout = timeout or self._config.command_timeout

        logger.info("执行命令: %s", command[:100])

        try:
            # asyncssh.run() 不支持 cwd/env 参数，用 shell 包装实现
            wrapped_cmd = command
            if env:
                env_prefix = " ".join(f"{k}={v}" for k, v in env.items())
                wrapped_cmd = f"export {env_prefix} && {wrapped_cmd}"
            if cwd:
                wrapped_cmd = f"cd '{cwd}' && {wrapped_cmd}"

            result = await asyncio.wait_for(
                self._conn.run(wrapped_cmd),
                timeout=cmd_timeout,
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = result.exit_status if result.exit_status is not None else -1

            # 截断输出
            stdout = self._truncate_output(stdout)
            stderr = self._truncate_output(stderr)

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
            }
        except asyncio.TimeoutError:
            logger.warning("命令执行超时: %s", command[:100])
            return {
                "stdout": "",
                "stderr": f"命令执行超时（{cmd_timeout}秒）",
                "exit_code": -1,
            }
        except Exception as e:
            logger.error("命令执行失败: %s", str(e))
            return {
                "stdout": "",
                "stderr": f"命令执行失败: {str(e)}",
                "exit_code": -1,
            }

    def _truncate_output(self, output: str) -> str:
        """截断过长的输出。"""
        max_size = self._config.max_output_size
        if len(output) > max_size:
            truncated = output[:max_size]
            return truncated + f"\n\n[输出已截断，原始大小 {len(output)} 字节，超过限制 {max_size} 字节]"
        return output

    async def read_file(self, path: str) -> dict[str, Any]:
        """读取远程文件内容。"""
        await self.ensure_connected()

        try:
            async with self._conn.start_sftp_client() as sftp:
                stat = await sftp.stat(path)
                if stat.size > self._config.max_read_size:
                    return {
                        "success": False,
                        "error": f"文件过大（{stat.size} 字节），超过限制 {self._config.max_read_size} 字节",
                    }

                async with sftp.open(path, "r") as f:
                    content = await f.read()

                content_str = content.decode("utf-8", errors="replace")
                return {"success": True, "content": content_str, "size": stat.size}
        except FileNotFoundError:
            return {"success": False, "error": f"文件不存在: {path}"}
        except PermissionError:
            return {"success": False, "error": f"权限不足: {path}"}
        except Exception as e:
            return {"success": False, "error": f"读取文件失败: {str(e)}"}

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """写入远程文件。"""
        await self.ensure_connected()

        try:
            async with self._conn.start_sftp_client() as sftp:
                async with sftp.open(path, "w") as f:
                    await f.write(content.encode("utf-8"))
            return {"success": True}
        except PermissionError:
            return {"success": False, "error": f"权限不足: {path}"}
        except Exception as e:
            return {"success": False, "error": f"写入文件失败: {str(e)}"}

    async def list_dir(self, path: str) -> dict[str, Any]:
        """列出目录内容。"""
        await self.ensure_connected()

        try:
            async with self._conn.start_sftp_client() as sftp:
                entries = []
                async for entry in sftp.scandir(path):
                    entries.append(
                        {
                            "name": entry.filename,
                            "type": "directory" if entry.is_dir() else "file",
                            "size": entry.size if not entry.is_dir() else 0,
                            "mtime": entry.mtime,
                        }
                    )
                return {"success": True, "entries": entries}
        except FileNotFoundError:
            return {"success": False, "error": f"目录不存在: {path}"}
        except NotADirectoryError:
            return {"success": False, "error": f"不是目录: {path}"}
        except PermissionError:
            return {"success": False, "error": f"权限不足: {path}"}
        except Exception as e:
            return {"success": False, "error": f"列出目录失败: {str(e)}"}

    async def file_exists(self, path: str) -> bool:
        """检查远程文件是否存在。"""
        await self.ensure_connected()
        try:
            async with self._conn.start_sftp_client() as sftp:
                await sftp.stat(path)
                return True
        except FileNotFoundError:
            return False

    async def move_to_trash(
        self, source_path: str, trash_subdir: str
    ) -> dict[str, Any]:
        """将文件移动到回收站目录。

        Args:
            source_path: 源文件路径
            trash_subdir: 回收站子目录路径（已创建好的）
        """
        await self.ensure_connected()

        filename = source_path.rsplit("/", 1)[-1]
        dest_path = f"{trash_subdir}/{filename}"

        try:
            result = await self.execute(f"mv '{source_path}' '{dest_path}'")
            if result["exit_code"] == 0:
                return {"success": True, "trash_path": dest_path}
            else:
                return {"success": False, "error": result["stderr"]}
        except Exception as e:
            return {"success": False, "error": f"移动到回收站失败: {str(e)}"}

    async def upload(self, local_path: str, remote_path: str) -> dict[str, Any]:
        """上传本地文件到远程主机。"""
        await self.ensure_connected()

        import os as local_os

        if not local_os.path.exists(local_path):
            return {"success": False, "error": f"本地文件不存在: {local_path}"}

        file_size = local_os.path.getsize(local_path)
        if file_size > self._config.max_upload_size:
            return {
                "success": False,
                "error": f"文件过大（{file_size} 字节），超过限制 {self._config.max_upload_size} 字节",
            }

        try:
            async with self._conn.start_sftp_client() as sftp:
                await sftp.put(local_path, remote_path)
            return {"success": True}
        except PermissionError:
            return {"success": False, "error": f"权限不足: {remote_path}"}
        except Exception as e:
            return {"success": False, "error": f"上传文件失败: {str(e)}"}

    async def download(self, remote_path: str, local_path: str) -> dict[str, Any]:
        """从远程主机下载文件到本地。"""
        await self.ensure_connected()

        try:
            async with self._conn.start_sftp_client() as sftp:
                await sftp.get(remote_path, local_path)
            return {"success": True}
        except FileNotFoundError:
            return {"success": False, "error": f"远程文件不存在: {remote_path}"}
        except PermissionError:
            return {"success": False, "error": f"权限不足: {remote_path}"}
        except Exception as e:
            return {"success": False, "error": f"下载文件失败: {str(e)}"}
