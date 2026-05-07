## 1. Project Setup

- [x] 1.1 Create project structure: `src/linux_ssh_mcp/` with `__init__.py`, `server.py`, `config.py`, `ssh_client.py`, `safety.py`, `audit.py`, `trash.py`, `tools/`
- [x] 1.2 Create `pyproject.toml` with dependencies: `mcp`, `asyncssh`, `pydantic`
- [x] 1.3 Create `README.md` with installation and usage instructions
- [x] 1.4 Create example config file `config.example.json`

## 2. Configuration Module

- [x] 2.1 Implement `config.py` with `Config` pydantic model (host, port, username, password, key_file, timeout, max_output_size, trash_dir, audit_log_path, max_trash_size, max_audit_size, etc.)
- [x] 2.2 Implement config loading from JSON file
- [x] 2.3 Implement environment variable overrides (SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD, SSH_KEY_FILE, MCP_TRASH_DIR, MCP_AUDIT_LOG)
- [x] 2.4 Add config validation with clear error messages for missing required fields

## 3. SSH Client Module

- [x] 3.1 Implement `ssh_client.py` with `SSHClient` class using `asyncssh`
- [x] 3.2 Implement `connect()` method with key and password auth support
- [x] 3.3 Implement `disconnect()` method for graceful connection close
- [x] 3.4 Implement `ensure_connected()` with lazy connect and auto-reconnect logic
- [x] 3.5 Implement `execute()` method for running shell commands with timeout, cwd, env vars
- [x] 3.6 Implement SFTP methods: `read_file()`, `write_file()`, `list_dir()`, `move_to_trash()`, `upload()`, `download()`
- [x] 3.7 Add output size truncation for command results and file reads

## 4. Safety Layer - Audit Logging

- [x] 4.1 Implement `audit.py` with `AuditLogger` class: append JSON Lines to `~/.linux_mcp_audit.log`
- [x] 4.2 Implement audit record format: timestamp, operation, params, result, exit_code, rollback_id
- [x] 4.3 Implement `get_audit_log` MCP tool: read and filter audit entries
- [x] 4.4 Implement audit log rotation when exceeding max size

## 5. Safety Layer - Trash Management

- [x] 5.1 Implement `trash.py` with `TrashManager` class: manage `~/.linux_mcp_trash/` directory
- [x] 5.2 Implement trash entry creation: timestamped subdirectory + `.index.json` update
- [x] 5.3 Implement `list_trash` MCP tool: list trash contents with metadata
- [x] 5.4 Implement `restore_file` MCP tool: restore file from trash to original path
- [x] 5.5 Implement `empty_trash` MCP tool: permanently delete all trash (requires confirmation)
- [x] 5.6 Implement trash size warning when exceeding threshold

## 6. Safety Layer - Command Classification

- [x] 6.1 Implement `safety.py` with `CommandClassifier`: classify commands as safe/dangerous/irreversible
- [x] 6.2 Implement safe command patterns: ls, cat, grep, find, stat, head, tail, ps, df, du, free, uptime, uname, whoami, id, pwd, which, echo (no redirect), wc
- [x] 6.3 Implement dangerous command patterns: rm, mv, dd, mkfs, fdisk, apt, yum, dnf, pip, npm, chmod, chown, useradd, systemctl, service, >, >>
- [x] 6.4 Implement path risk weighting: /tmp/ low risk, /etc/ /boot/ /usr/ high risk
- [x] 6.5 Implement `SafetyGate` class: pre-check before tool execution, post-record after

## 7. Safety Layer - Rollback Execution

- [x] 7.1 Implement `rollback_operation` MCP tool: rollback by audit entry ID
- [x] 7.2 Implement file operation rollback: restore from trash
- [x] 7.3 Implement command execution rollback: execute stored rollback_command
- [x] 7.4 Implement irreversible operation rejection for rollback attempts
- [x] 7.5 Record rollback operations in audit log

## 8. MCP Tools - Command Execution

- [x] 8.1 Implement `run_command` tool: execute shell command, return stdout/stderr/exit code
- [x] 8.2 Add optional parameters: `cwd`, `timeout`, `rollback_command`
- [x] 8.3 Integrate with SafetyGate: classify command, require rollback for dangerous commands

## 9. MCP Tools - File Operations

- [x] 9.1 Implement `read_file` tool: read remote file content
- [x] 9.2 Implement `write_file` tool: write content to remote file, backup old version to trash
- [x] 9.3 Implement `list_directory` tool: list directory contents with metadata
- [x] 9.4 Implement `delete_file` tool: move file to trash instead of permanent delete
- [x] 9.5 Implement `upload_file` tool: upload local file, backup existing remote file to trash
- [x] 9.6 Implement `download_file` tool: download remote file to local path

## 10. MCP Tools - Process Management

- [x] 10.1 Implement `list_processes` tool: list running processes with optional name filter
- [x] 10.2 Implement `kill_process` tool: kill process by PID, require `confirm_destructive` flag
- [x] 10.3 Implement `kill_process_by_name` tool: kill processes by name, require `confirm_destructive` flag

## 11. MCP Tools - System Info

- [x] 11.1 Implement `get_system_info` tool: return CPU, memory, disk, OS, uptime in one call
- [x] 11.2 Implement individual info tools: `get_cpu_info`, `get_memory_info`, `get_disk_info`, `get_os_info`, `get_uptime`

## 12. MCP Server Entry Point

- [x] 12.1 Implement `server.py` with MCP server setup, tool registration, and stdio transport
- [x] 12.2 Implement server lifecycle: load config on startup, init safety layer, connect SSH on first use, disconnect on shutdown
- [x] 12.3 Add `__main__.py` for `python -m linux_ssh_mcp` entry point
- [x] 12.4 Add console script entry point in `pyproject.toml`

## 13. Error Handling & Polish

- [x] 13.1 Wrap all tool handlers with try/except, return user-friendly error messages
- [x] 13.2 Add logging with configurable log level
- [x] 13.3 Add connection health check before each tool execution
- [x] 13.4 Test with Claude Desktop MCP configuration example
