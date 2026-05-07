"""审计日志模块 - 记录所有操作到远程主机上的审计日志文件。"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .config import Config
from .ssh_client import SSHClient

logger = logging.getLogger(__name__)


class AuditLogger:
    """审计日志记录器，将操作记录以 JSON Lines 格式写入远程主机。"""

    def __init__(self, config: Config, ssh_client: SSHClient):
        self._config = config
        self._ssh = ssh_client
        self._log_path = config.audit_log_path_expanded

    async def log(
        self,
        operation: str,
        params: dict[str, Any],
        result: str,
        exit_code: Optional[int] = None,
        rollback_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> str:
        """记录一条操作到审计日志。

        Returns:
            审计条目 ID（时间戳）
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        entry_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        record = {
            "id": entry_id,
            "timestamp": timestamp,
            "operation": operation,
            "params": params,
            "result": result,
        }

        if exit_code is not None:
            record["exit_code"] = exit_code
        if rollback_id is not None:
            record["rollback_id"] = rollback_id
        if error is not None:
            record["error"] = error

        line = json.dumps(record, ensure_ascii=False) + "\n"

        try:
            # 检查是否需要轮转
            await self._maybe_rotate()

            # 追加到日志文件
            await self._ssh.execute(
                f"printf '%s' '{line}' >> '{self._log_path}'"
            )
            logger.debug("审计日志已记录: %s %s", operation, entry_id)
        except Exception as e:
            logger.error("审计日志记录失败: %s", str(e))

        return entry_id

    async def _maybe_rotate(self) -> None:
        """检查并在需要时轮转审计日志。"""
        result = await self._ssh.execute(
            f"test -f '{self._log_path}' && wc -c < '{self._log_path}' || echo 0"
        )
        try:
            size = int(result["stdout"].strip())
        except (ValueError, KeyError):
            return

        if size > self._config.max_audit_size:
            logger.info("审计日志超过 %d 字节，执行轮转", self._config.max_audit_size)
            await self._ssh.execute(
                f"mv '{self._log_path}' '{self._log_path}.1'"
            )

    async def get_entries(
        self,
        operation: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """查询审计日志条目。

        Args:
            operation: 按操作类型过滤
            since: 起始时间（ISO 8601）
            until: 结束时间（ISO 8601）
            limit: 返回条数限制
        """
        result = await self._ssh.execute(
            f"test -f '{self._log_path}' && tail -n {limit * 2} '{self._log_path}' || echo ''"
        )

        if not result["stdout"].strip():
            return {"success": True, "entries": []}

        entries = []
        for line in result["stdout"].strip().split("\n"):
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                continue

        # 过滤
        if operation:
            entries = [e for e in entries if e.get("operation") == operation]
        if since:
            entries = [e for e in entries if e.get("timestamp", "") >= since]
        if until:
            entries = [e for e in entries if e.get("timestamp", "") <= until]

        # 取最近 limit 条
        entries = entries[-limit:]

        return {"success": True, "entries": entries}

    async def get_entry(self, entry_id: str) -> Optional[dict[str, Any]]:
        """根据 ID 获取单条审计记录。"""
        result = await self._ssh.execute(
            f"test -f '{self._log_path}' && grep '\"id\":\"{entry_id}\"' '{self._log_path}' || echo ''"
        )
        line = result["stdout"].strip()
        if line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass
        return None
