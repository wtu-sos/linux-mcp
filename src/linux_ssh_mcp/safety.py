"""安全层模块 - 命令分类、安全网关、回滚执行。"""

import logging
import re
from typing import Any, Optional

from .audit import AuditLogger
from .config import ServerConfig
from .ssh_client import SSHClient
from .trash import TrashManager

logger = logging.getLogger(__name__)

# 安全命令模式（只读操作）
SAFE_COMMANDS = [
    "ls", "cat", "grep", "find", "stat", "head", "tail",
    "ps", "df", "du", "free", "uptime", "uname", "whoami",
    "id", "pwd", "which", "echo", "wc", "less", "more",
    "journalctl", "systemctl status", "systemctl list",
    "ip addr", "ip link", "ip route", "ss ", "netstat",
    "lsof", "pgrep", "pidof",
]

# 禁止命令（应使用专用工具，如 delete_file）
BLOCKED_COMMANDS = [
    "rm ", "rmdir ", "unlink ",
]

# 危险命令模式（需要回滚命令）
DANGEROUS_COMMANDS = [
    "mv ", "dd ", "mkfs", "fdisk", "parted",
    "apt ", "apt-get ", "yum ", "dnf ", "zypper ",
    "pip install", "pip uninstall", "npm install", "npm uninstall",
    "chmod ", "chown ", "useradd ", "usermod ", "userdel ",
    "groupadd ", "groupmod ", "groupdel ",
    "systemctl start", "systemctl stop", "systemctl restart",
    "systemctl enable", "systemctl disable", "systemctl mask",
    "service ", ">", ">>", "tee ",
    "mount ", "umount ", "ln -s", "ln --symbolic",
    "crontab ", "sed -i", "awk -i",
    "tar ", "gzip ", "bzip2 ", "xz ",
    "make ", "cmake ", "gcc ", "g++",
    "docker ", "kubectl ", "podman ",
    "iptables ", "firewall-cmd ", "ufw ",
    "shutdown", "reboot", "halt", "poweroff",
    "curl ", "wget ",
]

# 高风险路径
HIGH_RISK_PATHS = [
    "/etc/", "/boot/", "/usr/", "/bin/", "/sbin/",
    "/lib/", "/lib64/", "/sys/", "/proc/", "/dev/",
    "/root/", "/home/*/", "/var/lib/", "/var/spool/",
]

# 低风险路径
LOW_RISK_PATHS = [
    "/tmp/", "/var/tmp/", "/dev/shm/",
]


class CommandClassifier:
    """命令危险度分类器。"""

    @staticmethod
    def classify(command: str) -> str:
        """分类命令：safe / dangerous / blocked / irreversible。

        Returns:
            "safe": 安全命令，可直接执行
            "dangerous": 危险命令，需要回滚命令
            "blocked": 禁止命令，应使用专用工具
            "irreversible": 不可逆命令，需要确认
        """
        cmd_stripped = command.strip()

        # 检查是否是禁止命令（应使用专用工具）
        for blocked_pattern in BLOCKED_COMMANDS:
            if blocked_pattern in cmd_stripped:
                return "blocked"

        # 检查是否是安全命令
        for safe_pattern in SAFE_COMMANDS:
            if cmd_stripped.startswith(safe_pattern):
                # 检查是否有重定向（echo hello > file 是危险的）
                if ">" in cmd_stripped:
                    return "dangerous"
                return "safe"

        # 检查是否是危险命令
        for dangerous_pattern in DANGEROUS_COMMANDS:
            if dangerous_pattern in cmd_stripped:
                return "dangerous"

        # 默认：未知命令视为危险
        return "dangerous"

    @staticmethod
    def check_path_risk(command: str) -> str:
        """检查命令中的路径风险等级。

        Returns:
            "high": 高风险路径
            "low": 低风险路径
            "normal": 普通路径
        """
        # 提取命令中的路径
        paths = re.findall(r'(/[^\s;|&]+)', command)

        for path in paths:
            for high_risk in HIGH_RISK_PATHS:
                if path.startswith(high_risk.rstrip("*")):
                    return "high"

        for path in paths:
            for low_risk in LOW_RISK_PATHS:
                if path.startswith(low_risk):
                    return "low"

        return "normal"

    @staticmethod
    def escalate_if_needed(base_classification: str, command: str) -> str:
        """根据路径风险升级分类。

        如果命令操作高风险路径，将 safe 升级为 dangerous。
        """
        if base_classification == "safe":
            path_risk = CommandClassifier.check_path_risk(command)
            if path_risk == "high":
                return "dangerous"
        return base_classification


class SafetyGate:
    """安全网关 - 所有工具调用的前置检查和后置记录。"""

    def __init__(
        self,
        config: ServerConfig,
        ssh_client: SSHClient,
        audit_logger: AuditLogger,
        trash_manager: TrashManager,
    ):
        self._config = config
        self._ssh = ssh_client
        self._audit = audit_logger
        self._trash = trash_manager
        self._classifier = CommandClassifier()

    async def pre_check_command(
        self, command: str, rollback_command: Optional[str] = None
    ) -> dict[str, Any]:
        """命令执行前检查。

        Returns:
            dict with "allowed": bool, "reason": str (if not allowed)
        """
        base_class = self._classifier.classify(command)
        classification = self._classifier.escalate_if_needed(base_class, command)

        if classification == "safe":
            return {"allowed": True}

        if classification == "blocked":
            return {
                "allowed": False,
                "reason": (
                    f"禁止直接执行删除命令。请使用 delete_file 工具，"
                    f"文件将被移入回收站，可随时恢复。"
                ),
            }

        if classification == "dangerous":
            if not rollback_command or not self._is_valid_rollback(rollback_command):
                return {
                    "allowed": False,
                    "reason": (
                        f"危险命令需要提供有效的回滚命令。命令分类: {classification}。"
                        f"请提供 rollback_command 参数（不能为空或无效命令）。"
                    ),
                }
            return {"allowed": True, "classification": classification}

        return {"allowed": True}

    @staticmethod
    def _is_valid_rollback(rollback_command: str) -> bool:
        """验证回滚命令是否有效。

        拒绝 trivial 回滚命令（echo、true、: 等无操作命令）。
        """
        cmd = rollback_command.strip()
        if not cmd:
            return False

        # 拒绝纯无操作命令
        trivial_patterns = [
            "echo", "true", ":", "false",
        ]
        for pattern in trivial_patterns:
            if cmd == pattern or cmd.startswith(pattern + " "):
                return False

        return True

    async def pre_check_destructive(self) -> dict[str, Any]:
        """不可逆操作前检查（需要 confirm_destructive）。"""
        return {
            "allowed": False,
            "reason": "此操作不可逆。请设置 confirm_destructive=true 以继续。",
        }

    async def post_record(
        self,
        operation: str,
        params: dict[str, Any],
        result: str,
        exit_code: Optional[int] = None,
        rollback_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> str:
        """操作后记录审计日志。"""
        return await self._audit.log(
            operation=operation,
            params=params,
            result=result,
            exit_code=exit_code,
            rollback_id=rollback_id,
            error=error,
        )

    async def rollback_operation(self, entry_id: str) -> dict[str, Any]:
        """回滚指定操作。

        Args:
            entry_id: 审计日志条目 ID
        """
        entry = await self._audit.get_entry(entry_id)
        if entry is None:
            return {"success": False, "error": f"操作记录不存在: {entry_id}"}

        operation = entry.get("operation", "")
        params = entry.get("params", {})

        # 文件操作回滚：从回收站恢复
        if operation in ("delete_file", "write_file", "upload_file"):
            rollback_id = entry.get("rollback_id")
            if not rollback_id:
                return {
                    "success": False,
                    "error": f"操作 {operation} 没有关联的回收站条目，无法回滚",
                }
            result = await self._trash.restore_file(rollback_id)
            if result["success"]:
                await self._audit.log(
                    operation="rollback",
                    params={"original_entry_id": entry_id, "rollback_id": rollback_id},
                    result="success",
                )
            return result

        # 命令执行回滚：执行存储的回滚命令
        if operation == "run_command":
            rollback_cmd = params.get("rollback_command")
            if not rollback_cmd:
                return {
                    "success": False,
                    "error": "该命令没有提供回滚命令，无法回滚",
                }
            result = await self._ssh.execute(rollback_cmd)
            await self._audit.log(
                operation="rollback",
                params={
                    "original_entry_id": entry_id,
                    "rollback_command": rollback_cmd,
                },
                result="success" if result["exit_code"] == 0 else "error",
                exit_code=result["exit_code"],
            )
            return {
                "success": result["exit_code"] == 0,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "exit_code": result["exit_code"],
            }

        # 不可逆操作
        if operation in ("kill_process", "kill_process_by_name"):
            return {
                "success": False,
                "error": "此操作不可逆，无法回滚",
            }

        return {"success": False, "error": f"不支持回滚的操作类型: {operation}"}
