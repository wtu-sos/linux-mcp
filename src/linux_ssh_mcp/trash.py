"""回收站管理模块 - 管理远程主机上的回收站目录。"""

import json
import logging
import random
import string
from datetime import datetime
from typing import Any, Optional

from .config import Config
from .ssh_client import SSHClient

logger = logging.getLogger(__name__)


class TrashManager:
    """回收站管理器，管理 ~/.linux_mcp_trash/ 目录。"""

    def __init__(self, config: Config, ssh_client: SSHClient):
        self._config = config
        self._ssh = ssh_client
        self._trash_dir = config.trash_dir_expanded
        self._index_path = f"{self._trash_dir}/.index.json"

    async def _ensure_trash_dir(self) -> None:
        """确保回收站目录和索引文件存在。"""
        await self._ssh.execute(f"mkdir -p '{self._trash_dir}'")
        result = await self._ssh.execute(
            f"test -f '{self._index_path}' && echo exists || echo missing"
        )
        if "missing" in result["stdout"]:
            await self._ssh.execute(
                f"echo '{{\"entries\":[]}}' > '{self._index_path}'"
            )
            logger.info("回收站索引文件已创建: %s", self._index_path)

    async def _read_index(self) -> list[dict[str, Any]]:
        """读取回收站索引。"""
        await self._ensure_trash_dir()
        result = await self._ssh.read_file(self._index_path)
        if result["success"]:
            try:
                data = json.loads(result["content"])
                return data.get("entries", [])
            except json.JSONDecodeError:
                logger.warning("回收站索引文件损坏，重新初始化")
                await self._ssh.execute(
                    f"echo '{{\"entries\":[]}}' > '{self._index_path}'"
                )
                return []
        return []

    async def _write_index(self, entries: list[dict[str, Any]]) -> None:
        """写入回收站索引。"""
        data = json.dumps({"entries": entries}, ensure_ascii=False, indent=2)
        await self._ssh.write_file(self._index_path, data)

    def _generate_id(self) -> str:
        """生成回收站条目 ID。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"{timestamp}_{random_suffix}"

    async def move_to_trash(
        self, source_path: str, operation: str
    ) -> dict[str, Any]:
        """将文件移动到回收站。

        Args:
            source_path: 源文件路径
            operation: 操作类型 (delete_file, write_file_backup, upload_backup)

        Returns:
            dict with success, entry_id, trash_path
        """
        await self._ensure_trash_dir()

        entry_id = self._generate_id()
        trash_subdir = f"{self._trash_dir}/{entry_id}"

        # 创建回收站子目录
        await self._ssh.execute(f"mkdir -p '{trash_subdir}'")

        # 移动文件
        result = await self._ssh.move_to_trash(source_path, trash_subdir)
        if not result["success"]:
            # 清理空目录
            await self._ssh.execute(f"rmdir '{trash_subdir}' 2>/dev/null")
            return result

        # 更新索引
        entries = await self._read_index()
        entries.append(
            {
                "id": entry_id,
                "original_path": source_path,
                "operation": operation,
                "timestamp": datetime.now().isoformat(),
                "rolled_back": False,
            }
        )
        await self._write_index(entries)

        logger.info("文件已移入回收站: %s -> %s", source_path, entry_id)
        return {"success": True, "entry_id": entry_id, "trash_path": result["trash_path"]}

    async def list_trash(
        self, include_rolled_back: bool = True
    ) -> dict[str, Any]:
        """列出回收站内容。"""
        entries = await self._read_index()
        if not include_rolled_back:
            entries = [e for e in entries if not e.get("rolled_back", False)]
        return {"success": True, "entries": entries}

    async def restore_file(
        self, entry_id: str, target_path: Optional[str] = None
    ) -> dict[str, Any]:
        """从回收站恢复文件。

        Args:
            entry_id: 回收站条目 ID
            target_path: 恢复目标路径（默认使用原始路径）
        """
        entries = await self._read_index()

        entry = None
        for e in entries:
            if e["id"] == entry_id:
                entry = e
                break

        if entry is None:
            return {"success": False, "error": f"回收站条目不存在: {entry_id}"}

        if entry.get("rolled_back", False):
            return {"success": False, "error": "该条目已回滚"}

        original_path = entry["original_path"]
        restore_path = target_path or original_path

        # 检查目标路径是否已存在
        exists = await self._ssh.file_exists(restore_path)
        if exists:
            return {
                "success": False,
                "error": f"目标路径已存在: {restore_path}，请指定其他目标路径",
            }

        # 从回收站移回
        trash_subdir = f"{self._trash_dir}/{entry_id}"
        list_result = await self._ssh.list_dir(trash_subdir)
        if not list_result["success"] or not list_result["entries"]:
            return {"success": False, "error": "回收站条目文件丢失"}

        filename = list_result["entries"][0]["name"]
        trash_file = f"{trash_subdir}/{filename}"

        # 确保目标目录存在
        target_dir = restore_path.rsplit("/", 1)[0] if "/" in restore_path else "."
        await self._ssh.execute(f"mkdir -p '{target_dir}'")

        result = await self._ssh.execute(f"mv '{trash_file}' '{restore_path}'")
        if result["exit_code"] != 0:
            return {"success": False, "error": f"恢复失败: {result['stderr']}"}

        # 清理回收站子目录
        await self._ssh.execute(f"rmdir '{trash_subdir}' 2>/dev/null")

        # 更新索引
        for e in entries:
            if e["id"] == entry_id:
                e["rolled_back"] = True
                e["restored_at"] = datetime.now().isoformat()
                e["restored_to"] = restore_path
                break
        await self._write_index(entries)

        logger.info("文件已从回收站恢复: %s -> %s", entry_id, restore_path)
        return {"success": True, "restored_to": restore_path}

    async def empty_trash(self) -> dict[str, Any]:
        """清空回收站（永久删除所有内容）。"""
        entries = await self._read_index()

        # 删除所有子目录
        for entry in entries:
            trash_subdir = f"{self._trash_dir}/{entry['id']}"
            await self._ssh.execute(f"rm -rf '{trash_subdir}'")

        # 重置索引
        await self._write_index([])

        logger.info("回收站已清空")
        return {"success": True, "deleted_count": len(entries)}

    async def get_trash_size(self) -> int:
        """获取回收站总大小（字节）。"""
        result = await self._ssh.execute(
            f"du -sb '{self._trash_dir}' 2>/dev/null | cut -f1 || echo 0"
        )
        try:
            return int(result["stdout"].strip())
        except (ValueError, KeyError):
            return 0

    async def check_size_warning(self) -> Optional[str]:
        """检查回收站大小是否超过警告阈值。"""
        size = await self.get_trash_size()
        if size > self._config.max_trash_size:
            size_mb = size / (1024 * 1024)
            threshold_mb = self._config.max_trash_size / (1024 * 1024)
            return (
                f"⚠️ 回收站大小 ({size_mb:.1f}MB) 已超过警告阈值 ({threshold_mb:.0f}MB)，"
                f"建议使用 empty_trash 清理"
            )
        return None
