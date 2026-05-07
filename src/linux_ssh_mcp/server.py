"""MCP 服务器入口 - 工具注册、服务器生命周期管理。"""

import argparse
import asyncio
import copy
import logging
import sys
from dataclasses import dataclass
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .audit import AuditLogger
from .config import AppConfig, ServerConfig, load_config
from .safety import SafetyGate
from .ssh_client import SSHClient
from .trash import TrashManager

logger = logging.getLogger(__name__)

# 全局状态
_app_config: Optional[AppConfig] = None
_contexts: dict[str, "ServerContext"] = {}


@dataclass
class ServerContext:
    """单台服务器的完整上下文。"""
    config: ServerConfig
    ssh: SSHClient
    audit: AuditLogger
    trash: TrashManager
    safety: SafetyGate


def get_context(name: str) -> ServerContext:
    """获取指定服务器的上下文。"""
    ctx = _contexts.get(name)
    if ctx is None:
        raise ValueError(f"服务器 '{name}' 未初始化")
    return ctx


def resolve_server(server_name: Optional[str]) -> str:
    """解析并验证 server_name。

    单服务器模式：自动返回默认名称。
    多服务器模式：必填，不存在则报错。
    """
    assert _app_config is not None

    if _app_config.is_single_server:
        return _app_config.default_name

    if not server_name:
        names = ", ".join(_app_config.server_names)
        raise ValueError(
            f"必须指定 server_name。可用服务器: {names}"
        )

    if server_name not in _contexts:
        names = ", ".join(_app_config.server_names)
        raise ValueError(
            f"服务器 '{server_name}' 不存在。可用服务器: {names}"
        )

    return server_name


# ============================================================
# MCP 工具处理函数
# ============================================================


async def handle_run_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
    rollback_command: Optional[str] = None,
    server_name: Optional[str] = None,
) -> str:
    """执行 Shell 命令。"""
    name = resolve_server(server_name)
    ctx = get_context(name)

    # 安全检查
    check = await ctx.safety.pre_check_command(command, rollback_command)
    if not check["allowed"]:
        await ctx.audit.log(
            operation="run_command",
            params={"command": command},
            result="rejected",
            error=check["reason"],
        )
        return f"❌ 命令被拒绝: {check['reason']}"

    # 执行命令
    result = await ctx.ssh.execute(command, cwd=cwd, timeout=timeout)

    # 记录审计日志
    await ctx.audit.log(
        operation="run_command",
        params={
            "command": command,
            "cwd": cwd,
            "rollback_command": rollback_command,
        },
        result="success" if result["exit_code"] == 0 else "error",
        exit_code=result["exit_code"],
    )

    output_parts = []
    if result["stdout"]:
        output_parts.append(f"📤 stdout:\n{result['stdout']}")
    if result["stderr"]:
        output_parts.append(f"📤 stderr:\n{result['stderr']}")
    output_parts.append(f"🔢 退出码: {result['exit_code']}")

    return "\n\n".join(output_parts)


async def handle_read_file(
    path: str,
    server_name: Optional[str] = None,
) -> str:
    """读取远程文件。"""
    name = resolve_server(server_name)
    ctx = get_context(name)

    result = await ctx.ssh.read_file(path)

    await ctx.audit.log(
        operation="read_file",
        params={"path": path},
        result="success" if result["success"] else "error",
        error=result.get("error"),
    )

    if result["success"]:
        return f"📄 {path} ({result['size']} 字节):\n\n{result['content']}"
    return f"❌ {result['error']}"


async def handle_write_file(
    path: str,
    content: str,
    server_name: Optional[str] = None,
) -> str:
    """写入远程文件（覆盖前备份旧版本到回收站）。"""
    name = resolve_server(server_name)
    ctx = get_context(name)

    # 如果文件已存在，先备份到回收站
    rollback_id = None
    exists = await ctx.ssh.file_exists(path)
    if exists:
        backup_result = await ctx.trash.move_to_trash(path, "write_file_backup")
        if backup_result["success"]:
            rollback_id = backup_result["entry_id"]

    # 写入新内容
    result = await ctx.ssh.write_file(path, content)

    await ctx.audit.log(
        operation="write_file",
        params={"path": path, "size": len(content)},
        result="success" if result["success"] else "error",
        rollback_id=rollback_id,
        error=result.get("error"),
    )

    if result["success"]:
        msg = f"✅ 文件已写入: {path} ({len(content)} 字节)"
        if rollback_id:
            msg += f"\n📦 旧版本已备份到回收站: {rollback_id}"
        return msg
    return f"❌ {result['error']}"


async def handle_list_directory(
    path: str,
    server_name: Optional[str] = None,
) -> str:
    """列出目录内容。"""
    name = resolve_server(server_name)
    ctx = get_context(name)

    result = await ctx.ssh.list_dir(path)

    await ctx.audit.log(
        operation="list_directory",
        params={"path": path},
        result="success" if result["success"] else "error",
        error=result.get("error"),
    )

    if not result["success"]:
        return f"❌ {result['error']}"

    if not result["entries"]:
        return f"📂 {path} 是空目录"

    lines = [f"📂 {path} ({len(result['entries'])} 个条目):"]
    for entry in result["entries"]:
        icon = "📁" if entry["type"] == "directory" else "📄"
        size_str = f" {entry['size']}B" if entry["type"] == "file" else ""
        lines.append(f"  {icon} {entry['name']}{size_str}")

    return "\n".join(lines)


async def handle_delete_file(
    path: str,
    server_name: Optional[str] = None,
) -> str:
    """删除文件（移入回收站）。"""
    name = resolve_server(server_name)
    ctx = get_context(name)

    # 检查文件是否存在
    exists = await ctx.ssh.file_exists(path)
    if not exists:
        await ctx.audit.log(
            operation="delete_file",
            params={"path": path},
            result="error",
            error="文件不存在",
        )
        return f"❌ 文件不存在: {path}"

    # 移入回收站
    result = await ctx.trash.move_to_trash(path, "delete_file")

    await ctx.audit.log(
        operation="delete_file",
        params={"path": path},
        result="success" if result["success"] else "error",
        rollback_id=result.get("entry_id"),
        error=result.get("error"),
    )

    if result["success"]:
        return f"✅ 文件已移入回收站: {path}\n📦 回收站 ID: {result['entry_id']}"
    return f"❌ {result['error']}"


async def handle_upload_file(
    local_path: str,
    remote_path: str,
    server_name: Optional[str] = None,
) -> str:
    """上传本地文件到远程主机。"""
    name = resolve_server(server_name)
    ctx = get_context(name)

    # 如果远程文件已存在，备份
    rollback_id = None
    exists = await ctx.ssh.file_exists(remote_path)
    if exists:
        backup_result = await ctx.trash.move_to_trash(remote_path, "upload_backup")
        if backup_result["success"]:
            rollback_id = backup_result["entry_id"]

    result = await ctx.ssh.upload(local_path, remote_path)

    await ctx.audit.log(
        operation="upload_file",
        params={"local_path": local_path, "remote_path": remote_path},
        result="success" if result["success"] else "error",
        rollback_id=rollback_id,
        error=result.get("error"),
    )

    if result["success"]:
        msg = f"✅ 文件已上传: {local_path} -> {remote_path}"
        if rollback_id:
            msg += f"\n📦 远程旧文件已备份到回收站: {rollback_id}"
        return msg
    return f"❌ {result['error']}"


async def handle_download_file(
    remote_path: str,
    local_path: str,
    server_name: Optional[str] = None,
) -> str:
    """从远程主机下载文件。"""
    name = resolve_server(server_name)
    ctx = get_context(name)

    result = await ctx.ssh.download(remote_path, local_path)

    await ctx.audit.log(
        operation="download_file",
        params={"remote_path": remote_path, "local_path": local_path},
        result="success" if result["success"] else "error",
        error=result.get("error"),
    )

    if result["success"]:
        return f"✅ 文件已下载: {remote_path} -> {local_path}"
    return f"❌ {result['error']}"


async def handle_list_processes(
    name: Optional[str] = None,
    server_name: Optional[str] = None,
) -> str:
    """列出运行中的进程。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    if name:
        command = f"ps aux | grep -v grep | grep '{name}' | head -n 200"
    else:
        command = "ps aux --sort=-%cpu | head -n 200"

    result = await ctx.ssh.execute(command)

    await ctx.audit.log(
        operation="list_processes",
        params={"name": name},
        result="success",
    )

    if result["stdout"]:
        return f"📋 进程列表:\n\n```\n{result['stdout']}\n```"
    return "📋 没有找到匹配的进程"


async def handle_kill_process(
    pid: int,
    force: bool = False,
    confirm_destructive: bool = False,
    server_name: Optional[str] = None,
) -> str:
    """按 PID 终止进程。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    if not confirm_destructive:
        await ctx.audit.log(
            operation="kill_process",
            params={"pid": pid, "force": force},
            result="rejected",
            error="未确认不可逆操作",
        )
        return "❌ 此操作不可逆。请设置 confirm_destructive=true 以继续。"

    signal = "SIGKILL" if force else "SIGTERM"
    result = await ctx.ssh.execute(f"kill -{signal} {pid}")

    await ctx.audit.log(
        operation="kill_process",
        params={"pid": pid, "force": force},
        result="success" if result["exit_code"] == 0 else "error",
        exit_code=result["exit_code"],
        error=result["stderr"] if result["exit_code"] != 0 else None,
    )

    if result["exit_code"] == 0:
        return f"✅ 已向进程 {pid} 发送 {signal}"
    return f"❌ 终止进程失败: {result['stderr']}"


async def handle_kill_process_by_name(
    name: str,
    force: bool = False,
    confirm_destructive: bool = False,
    server_name: Optional[str] = None,
) -> str:
    """按名称终止进程。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    if not confirm_destructive:
        await ctx.audit.log(
            operation="kill_process_by_name",
            params={"name": name, "force": force},
            result="rejected",
            error="未确认不可逆操作",
        )
        return "❌ 此操作不可逆。请设置 confirm_destructive=true 以继续。"

    signal = "SIGKILL" if force else "SIGTERM"
    result = await ctx.ssh.execute(f"pkill -{signal} '{name}'")

    await ctx.audit.log(
        operation="kill_process_by_name",
        params={"name": name, "force": force},
        result="success" if result["exit_code"] == 0 else "error",
        exit_code=result["exit_code"],
        error=result["stderr"] if result["exit_code"] != 0 else None,
    )

    if result["exit_code"] == 0:
        return f"✅ 已向匹配 '{name}' 的进程发送 {signal}"
    return f"❌ 终止进程失败（可能没有匹配的进程）: {result['stderr']}"


async def handle_get_system_info(
    server_name: Optional[str] = None,
) -> str:
    """获取完整系统信息。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    commands = {
        "CPU": "lscpu | grep 'Model name\\|CPU(s)' | head -2 && top -bn1 | grep 'Cpu(s)' | head -1",
        "内存": "free -h",
        "磁盘": "df -h --type=ext4 --type=xfs --type=btrfs 2>/dev/null || df -h | head -20",
        "操作系统": "cat /etc/os-release 2>/dev/null | head -5 || uname -a",
        "运行时间": "uptime",
    }

    output_parts = ["📊 系统信息:\n"]
    for label, cmd in commands.items():
        result = await ctx.ssh.execute(cmd)
        if result["stdout"]:
            output_parts.append(f"### {label}\n```\n{result['stdout'].strip()}\n```")

    await ctx.audit.log(
        operation="get_system_info",
        params={},
        result="success",
    )

    return "\n".join(output_parts)


async def handle_get_cpu_info(
    server_name: Optional[str] = None,
) -> str:
    """获取 CPU 信息。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    result = await ctx.ssh.execute("lscpu | grep 'Model name\\|CPU(s)\\|Architecture' && top -bn1 | grep 'Cpu(s)' | head -1")
    await ctx.audit.log(operation="get_cpu_info", params={}, result="success")
    return f"🖥 CPU 信息:\n```\n{result['stdout'].strip()}\n```"


async def handle_get_memory_info(
    server_name: Optional[str] = None,
) -> str:
    """获取内存信息。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    result = await ctx.ssh.execute("free -h")
    await ctx.audit.log(operation="get_memory_info", params={}, result="success")
    return f"🧠 内存信息:\n```\n{result['stdout'].strip()}\n```"


async def handle_get_disk_info(
    server_name: Optional[str] = None,
) -> str:
    """获取磁盘信息。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    result = await ctx.ssh.execute("df -h | head -20")
    await ctx.audit.log(operation="get_disk_info", params={}, result="success")
    return f"💾 磁盘信息:\n```\n{result['stdout'].strip()}\n```"


async def handle_get_os_info(
    server_name: Optional[str] = None,
) -> str:
    """获取操作系统信息。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    result = await ctx.ssh.execute("cat /etc/os-release 2>/dev/null | head -10 || uname -a")
    await ctx.audit.log(operation="get_os_info", params={}, result="success")
    return f"🐧 操作系统信息:\n```\n{result['stdout'].strip()}\n```"


async def handle_get_uptime(
    server_name: Optional[str] = None,
) -> str:
    """获取系统运行时间。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    result = await ctx.ssh.execute("uptime")
    await ctx.audit.log(operation="get_uptime", params={}, result="success")
    return f"⏱ 运行时间:\n```\n{result['stdout'].strip()}\n```"


async def handle_get_audit_log(
    operation: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50,
    server_name: Optional[str] = None,
) -> str:
    """查看审计日志。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    result = await ctx.audit.get_entries(
        operation=operation, since=since, until=until, limit=limit
    )

    if not result["entries"]:
        return "📋 审计日志为空"

    lines = [f"📋 审计日志（最近 {len(result['entries'])} 条）:\n"]
    for entry in result["entries"]:
        op = entry.get("operation", "?")
        res = entry.get("result", "?")
        ts = entry.get("timestamp", "?")[:19]
        icon = "✅" if res == "success" else "❌" if res == "error" else "🚫"
        lines.append(f"  {icon} [{ts}] {op} - {res}")

    return "\n".join(lines)


async def handle_list_trash(
    include_rolled_back: bool = True,
    server_name: Optional[str] = None,
) -> str:
    """列出回收站内容。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    result = await ctx.trash.list_trash(include_rolled_back=include_rolled_back)

    if not result["entries"]:
        return "📦 回收站为空"

    lines = [f"📦 回收站内容（{len(result['entries'])} 个条目）:\n"]
    for entry in result["entries"]:
        icon = "↩️" if entry.get("rolled_back") else "📄"
        op = entry.get("operation", "?")
        path = entry.get("original_path", "?")
        ts = entry.get("timestamp", "?")[:19]
        lines.append(f"  {icon} [{entry['id']}] {op}: {path} ({ts})")

    # 检查大小警告
    warning = await ctx.trash.check_size_warning()
    if warning:
        lines.append(f"\n{warning}")

    return "\n".join(lines)


async def handle_restore_file(
    entry_id: str,
    target_path: Optional[str] = None,
    server_name: Optional[str] = None,
) -> str:
    """从回收站恢复文件。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    result = await ctx.trash.restore_file(entry_id, target_path=target_path)

    await ctx.audit.log(
        operation="restore_file",
        params={"entry_id": entry_id, "target_path": target_path},
        result="success" if result["success"] else "error",
        error=result.get("error"),
    )

    if result["success"]:
        return f"✅ 文件已恢复: {result['restored_to']}"
    return f"❌ {result['error']}"


async def handle_empty_trash(
    confirm_destructive: bool = False,
    server_name: Optional[str] = None,
) -> str:
    """清空回收站。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    if not confirm_destructive:
        await ctx.audit.log(
            operation="empty_trash",
            params={},
            result="rejected",
            error="未确认不可逆操作",
        )
        return "❌ 此操作不可逆。请设置 confirm_destructive=true 以继续。"

    result = await ctx.trash.empty_trash()

    await ctx.audit.log(
        operation="empty_trash",
        params={},
        result="success",
    )

    return f"✅ 回收站已清空，共删除 {result['deleted_count']} 个条目"


async def handle_rollback_operation(
    entry_id: str,
    server_name: Optional[str] = None,
) -> str:
    """回滚指定操作。"""
    srv_name = resolve_server(server_name)
    ctx = get_context(srv_name)

    result = await ctx.safety.rollback_operation(entry_id)

    if result["success"]:
        return f"✅ 操作已回滚: {entry_id}"
    return f"❌ {result['error']}"


async def handle_list_servers() -> str:
    """列出所有已配置的服务器。"""
    assert _app_config is not None

    lines = [f"📋 已配置服务器 ({len(_app_config.servers)}):\n"]
    for s in _app_config.servers:
        lines.append(f"  🖥 {s.name}: {s.host}:{s.port} ({s.username})")

    return "\n".join(lines)


# ============================================================
# 工具定义（基础模板，不含 server_name）
# ============================================================

_BASE_TOOLS = [
    Tool(
        name="run_command",
        description="在远程 Linux 主机上执行 Shell 命令。危险命令需要提供回滚命令。",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 Shell 命令"},
                "cwd": {"type": "string", "description": "工作目录（可选）"},
                "timeout": {"type": "integer", "description": "超时时间（秒，可选）"},
                "rollback_command": {"type": "string", "description": "回滚命令（危险命令必填）"},
            },
            "required": ["command"],
        },
    ),
    Tool(
        name="read_file",
        description="读取远程 Linux 主机上的文件内容。",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "远程文件路径"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="write_file",
        description="写入内容到远程 Linux 主机上的文件。如果文件已存在，旧版本会自动备份到回收站。",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "远程文件路径"},
                "content": {"type": "string", "description": "要写入的内容"},
            },
            "required": ["path", "content"],
        },
    ),
    Tool(
        name="list_directory",
        description="列出远程 Linux 主机上的目录内容。",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "远程目录路径"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="delete_file",
        description="删除远程 Linux 主机上的文件（移入回收站，可恢复）。",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要删除的文件路径"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="upload_file",
        description="上传本地文件到远程 Linux 主机。如果远程文件已存在，旧版本会自动备份到回收站。",
        inputSchema={
            "type": "object",
            "properties": {
                "local_path": {"type": "string", "description": "本地文件路径"},
                "remote_path": {"type": "string", "description": "远程目标路径"},
            },
            "required": ["local_path", "remote_path"],
        },
    ),
    Tool(
        name="download_file",
        description="从远程 Linux 主机下载文件到本地。",
        inputSchema={
            "type": "object",
            "properties": {
                "remote_path": {"type": "string", "description": "远程文件路径"},
                "local_path": {"type": "string", "description": "本地目标路径"},
            },
            "required": ["remote_path", "local_path"],
        },
    ),
    Tool(
        name="list_processes",
        description="列出远程 Linux 主机上运行中的进程。",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "按进程名称过滤（可选）"},
            },
        },
    ),
    Tool(
        name="kill_process",
        description="按 PID 终止远程 Linux 主机上的进程。此操作不可逆，需要 confirm_destructive=true。",
        inputSchema={
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "进程 PID"},
                "force": {"type": "boolean", "description": "是否强制终止（SIGKILL）"},
                "confirm_destructive": {"type": "boolean", "description": "确认执行不可逆操作"},
            },
            "required": ["pid", "confirm_destructive"],
        },
    ),
    Tool(
        name="kill_process_by_name",
        description="按名称终止远程 Linux 主机上的进程。此操作不可逆，需要 confirm_destructive=true。",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "进程名称"},
                "force": {"type": "boolean", "description": "是否强制终止（SIGKILL）"},
                "confirm_destructive": {"type": "boolean", "description": "确认执行不可逆操作"},
            },
            "required": ["name", "confirm_destructive"],
        },
    ),
    Tool(
        name="get_system_info",
        description="获取远程 Linux 主机的完整系统信息（CPU、内存、磁盘、操作系统、运行时间）。",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_cpu_info",
        description="获取远程 Linux 主机的 CPU 信息。",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_memory_info",
        description="获取远程 Linux 主机的内存信息。",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_disk_info",
        description="获取远程 Linux 主机的磁盘信息。",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_os_info",
        description="获取远程 Linux 主机的操作系统信息。",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_uptime",
        description="获取远程 Linux 主机的运行时间。",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_audit_log",
        description="查看审计日志，可按操作类型和时间范围过滤。",
        inputSchema={
            "type": "object",
            "properties": {
                "operation": {"type": "string", "description": "按操作类型过滤（可选）"},
                "since": {"type": "string", "description": "起始时间 ISO 8601（可选）"},
                "until": {"type": "string", "description": "结束时间 ISO 8601（可选）"},
                "limit": {"type": "integer", "description": "返回条数限制（默认 50）"},
            },
        },
    ),
    Tool(
        name="list_trash",
        description="列出回收站内容。",
        inputSchema={
            "type": "object",
            "properties": {
                "include_rolled_back": {"type": "boolean", "description": "是否包含已回滚的条目（默认 true）"},
            },
        },
    ),
    Tool(
        name="restore_file",
        description="从回收站恢复文件到原始路径或指定路径。",
        inputSchema={
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "回收站条目 ID"},
                "target_path": {"type": "string", "description": "恢复目标路径（可选，默认使用原始路径）"},
            },
            "required": ["entry_id"],
        },
    ),
    Tool(
        name="empty_trash",
        description="清空回收站（永久删除所有内容）。此操作不可逆，需要 confirm_destructive=true。",
        inputSchema={
            "type": "object",
            "properties": {
                "confirm_destructive": {"type": "boolean", "description": "确认执行不可逆操作"},
            },
            "required": ["confirm_destructive"],
        },
    ),
    Tool(
        name="rollback_operation",
        description="回滚指定操作（通过审计日志条目 ID）。支持文件操作和命令执行的回滚。",
        inputSchema={
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "审计日志条目 ID"},
            },
            "required": ["entry_id"],
        },
    ),
]

_LIST_SERVERS_TOOL = Tool(
    name="list_servers",
    description="列出所有已配置的服务器及其连接信息。",
    inputSchema={"type": "object", "properties": {}},
)

# 工具名 -> 处理函数映射
TOOL_HANDLERS = {
    "run_command": handle_run_command,
    "read_file": handle_read_file,
    "write_file": handle_write_file,
    "list_directory": handle_list_directory,
    "delete_file": handle_delete_file,
    "upload_file": handle_upload_file,
    "download_file": handle_download_file,
    "list_processes": handle_list_processes,
    "kill_process": handle_kill_process,
    "kill_process_by_name": handle_kill_process_by_name,
    "get_system_info": handle_get_system_info,
    "get_cpu_info": handle_get_cpu_info,
    "get_memory_info": handle_get_memory_info,
    "get_disk_info": handle_get_disk_info,
    "get_os_info": handle_get_os_info,
    "get_uptime": handle_get_uptime,
    "get_audit_log": handle_get_audit_log,
    "list_trash": handle_list_trash,
    "restore_file": handle_restore_file,
    "empty_trash": handle_empty_trash,
    "rollback_operation": handle_rollback_operation,
    "list_servers": handle_list_servers,
}


def _build_tools() -> list[Tool]:
    """根据服务器数量动态构建工具列表。"""
    assert _app_config is not None

    if _app_config.is_single_server:
        return list(_BASE_TOOLS)

    # 多服务器模式：每个工具加 server_name
    tools = []
    for base in _BASE_TOOLS:
        schema = copy.deepcopy(base.inputSchema)
        schema["properties"]["server_name"] = {
            "type": "string",
            "description": "目标服务器名称（必填）。使用 list_servers 查看可用服务器。",
        }
        schema["required"] = ["server_name"] + schema.get("required", [])
        description = base.description + " ⚠️ 必须指定 server_name 参数。"
        tools.append(Tool(name=base.name, description=description, inputSchema=schema))

    # 加 list_servers
    tools.append(_LIST_SERVERS_TOOL)

    return tools


# ============================================================
# 服务器生命周期
# ============================================================


async def init_components(config: AppConfig) -> None:
    """初始化所有组件。"""
    global _app_config, _contexts

    _app_config = config
    _contexts = {}

    for server_config in config.servers:
        ssh = SSHClient(server_config)
        audit = AuditLogger(server_config, ssh)
        trash = TrashManager(server_config, ssh)
        safety = SafetyGate(server_config, ssh, audit, trash)

        _contexts[server_config.name] = ServerContext(
            config=server_config,
            ssh=ssh,
            audit=audit,
            trash=trash,
            safety=safety,
        )
        logger.info("服务器 '%s' 已初始化 (%s@%s:%d)",
                     server_config.name, server_config.username,
                     server_config.host, server_config.port)


async def shutdown_components() -> None:
    """关闭所有组件。"""
    for name, ctx in _contexts.items():
        await ctx.ssh.disconnect()
        logger.info("服务器 '%s' SSH 连接已关闭", name)


def create_mcp_server() -> Server:
    """创建 MCP 服务器实例。"""
    server = Server("linux-ssh-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return _build_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            return [TextContent(type="text", text=f"❌ 未知工具: {name}")]

        try:
            result = await handler(**arguments)
            return [TextContent(type="text", text=str(result))]
        except ValueError as e:
            # resolve_server 抛出的验证错误
            return [TextContent(type="text", text=f"❌ {str(e)}")]
        except Exception as e:
            logger.exception("工具执行异常: %s", name)
            return [TextContent(type="text", text=f"❌ 工具执行异常: {str(e)}")]

    return server


async def run_server(config_path: str) -> None:
    """运行 MCP 服务器。"""
    config = load_config(config_path)
    await init_components(config)

    server = create_mcp_server()

    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP 服务器已启动 (stdio)")
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """入口函数。"""
    parser = argparse.ArgumentParser(description="Linux SSH MCP Server")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        required=True,
        help="JSON 配置文件路径（必填）",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        asyncio.run(run_server(args.config))
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.exception("服务器启动失败: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
