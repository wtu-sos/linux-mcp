## Why

AI assistants (Claude, Cursor, etc.) need a standard way to execute commands and manage files on remote Linux servers via SSH. Existing solutions require manual setup or lack MCP protocol support. This project provides a Python-based MCP server that bridges AI tools with remote Linux machines through SSH, enabling secure, programmatic remote system management.

Beyond basic remote operations, AI-driven system management introduces risk: a wrong command can cause irreversible damage. This server MUST provide a safety net — audit logging for all operations, a trash directory for deleted files, and rollback capability for reversible operations. Dangerous operations without a defined rollback path MUST be rejected.

## What Changes

- New Python MCP server project with SSH connectivity to remote Linux machines
- MCP tools for: command execution, file read/write/upload/download, process management, system info retrieval
- **Safety layer**: audit logging of all operations, trash directory for deleted/overwritten files, rollback execution
- **Command classification**: safe commands execute freely; dangerous commands require a rollback command; irreversible operations require explicit confirmation
- SSH key-based and password-based authentication support
- Session management with connection pooling and timeout handling
- Configuration via environment variables and/or config file
- Async I/O using `asyncssh` library for non-blocking SSH operations

## Capabilities

### New Capabilities
- `ssh-connection`: Establish and manage SSH connections to remote Linux hosts with key or password auth
- `command-execution`: Execute shell commands on remote host, return stdout/stderr/exit code; dangerous commands require rollback command
- `file-operations`: Read, write, list, and delete files on remote host; upload/download files via SFTP; deletions go to trash; writes backup old versions
- `process-management`: List running processes, kill processes by PID or name (irreversible, requires confirmation)
- `system-info`: Retrieve system information (CPU, memory, disk, OS version, uptime)
- `audit-logging`: Record all operations with timestamp, type, parameters, result; query audit log
- `trash-management`: Trash directory for deleted/overwritten files; list, restore, and empty trash
- `rollback-execution`: Execute rollback for reversible operations; track operation state

### Modified Capabilities
<!-- No existing capabilities to modify -->

## Impact

- New Python package: `linux-ssh-mcp` (or similar)
- Dependencies: `mcp`, `asyncssh`, `pydantic` (for config)
- No existing code affected — greenfield project
- Target Python version: 3.10+
- Distribution: PyPI package + source install
- Remote host requires: `~/.linux_mcp_trash/` directory (auto-created), `~/.linux_mcp_audit.log` file
