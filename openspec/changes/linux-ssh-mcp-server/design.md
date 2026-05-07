## Context

Greenfield Python project. No existing codebase. The MCP (Model Context Protocol) server will run locally and connect to remote Linux machines via SSH. AI clients (Claude Desktop, Cursor, etc.) communicate with the MCP server over stdio transport.

A critical design requirement: the server acts as a **safety gateway**, not a transparent proxy. All operations are audited, destructive file operations use a trash directory, and irreversible operations require explicit confirmation or a defined rollback path.

## Goals / Non-Goals

**Goals:**
- Provide MCP tools for common remote Linux operations: command execution, file management, process control, system info
- **Audit logging**: record every operation with timestamp, type, parameters, and result on the remote host
- **Trash directory**: deleted files and overwritten file versions move to `~/.linux_mcp_trash/` instead of being destroyed
- **Rollback**: file operations are automatically reversible; command execution requires a rollback command for dangerous operations
- **Command classification**: safe commands (read-only) execute freely; dangerous commands (write/delete/system) require rollback; irreversible operations (kill process) require confirmation
- Support both SSH key and password authentication
- Handle connection lifecycle (connect, reconnect, timeout, disconnect)
- Async I/O for non-blocking operations
- Clean error handling with meaningful messages back to AI
- Configurable via environment variables and JSON config file
- Python 3.10+ compatibility

**Non-Goals:**
- Multi-hop SSH / bastion host support (v1)
- Agent installation on remote host
- GUI or web interface
- Windows remote target support (Linux only)
- Docker/K8s container exec (use SSH into host instead)

## Decisions

### 1. SSH Library: `asyncssh` over `paramiko`

- **Choice**: `asyncssh`
- **Rationale**: Native async/await support, better performance for concurrent operations, cleaner API. `paramiko` requires thread pools for async usage.
- **Alternative**: `paramiko` — mature but synchronous, needs executor wrapper.

### 2. MCP Transport: stdio only

- **Choice**: stdio transport (default for MCP Python SDK)
- **Rationale**: Simplest integration with AI clients. No network port exposure needed. Follows MCP convention.
- **Alternative**: SSE/HTTP transport — adds complexity, not needed for local agent use.

### 3. Connection Management: Lazy singleton with reconnect

- **Choice**: Single persistent SSH connection per server instance, established on first tool call, with auto-reconnect on failure.
- **Rationale**: MCP server is per-session, one remote host at a time. Connection pooling overkill for single-target use case.
- **Alternative**: Connection pool — unnecessary complexity for single-host scenario.

### 4. Configuration: Env vars + JSON config file

- **Choice**: Environment variables for secrets (SSH password, key path), JSON config file for host/port/user/timeout. Env vars override config file.
- **Rationale**: Secrets should never be in config files. Env vars work well with Docker and systemd. Config file for non-sensitive defaults.
- **Alternative**: TOML/YAML config — JSON is simpler, no extra dependency.

### 5. File Transfer: SFTP via asyncssh

- **Choice**: Use `asyncssh` built-in SFTP client for file read/write/upload/download.
- **Rationale**: No extra dependency. SFTP is standard, secure, and sufficient for file operations.
- **Alternative**: SCP — less feature-rich, no directory listing.

### 6. Project Structure: Flat package layout

- **Choice**: `src/linux_ssh_mcp/` with `server.py`, `ssh_client.py`, `tools/`, `config.py`, `safety.py`, `audit.py`, `trash.py`
- **Rationale**: Simple, standard Python layout. Safety layer gets dedicated modules.

### 7. Safety Layer Architecture

- **Choice**: Intercept all tool calls through a `SafetyGate` class before execution.
- **Rationale**: Centralized safety enforcement. Each tool handler calls `safety_gate.pre_check()` before executing and `safety_gate.post_record()` after. No tool bypasses the gate.
- **Alternative**: Decorator-based — harder to manage state across operations.

### 8. Command Danger Classification: Hybrid pattern + path awareness

- **Choice**: Classify commands by operation pattern AND target path risk.
- **Rationale**: Pure pattern matching misses context (e.g., `rm /tmp/test` vs `rm /etc/nginx.conf`). Path risk weighting catches this.
- **Classification tiers**:
  - **Safe** (read-only): `ls`, `cat`, `grep`, `find`, `stat`, `head`, `tail`, `ps`, `df`, `du`, `free`, `uptime`, `uname`, `whoami`, `id`, `pwd`, `which`, `echo` (no redirect), `wc`
  - **State change** (needs rollback): `systemctl`, `service`, `kill`, `pkill`, `killall`
  - **File write** (auto-rollback via trash): `>`, `>>`, `tee`, `touch`, `mkdir`, `cp`, `mv`, `tar`, `gzip`
  - **File delete** (auto-rollback via trash): `rm`, `unlink`, `rmdir`
  - **System mutate** (must have rollback): `dd`, `mkfs`, `fdisk`, `apt`, `yum`, `dnf`, `pip`, `npm`, `chmod`, `chown`, `useradd`, `usermod`
- **Path risk weighting**: operations on `/tmp/`, `/var/tmp/` are lower risk; operations on `/etc/`, `/boot/`, `/usr/`, `/bin/`, `/sbin/` are higher risk.

### 9. Trash Directory Design

- **Choice**: `~/.linux_mcp_trash/` with timestamped subdirectories and a JSON index file.
- **Structure**:
  ```
  ~/.linux_mcp_trash/
  ├── .index.json
  ├── 20260507_174300_a1b2c3/
  │   └── nginx.conf          # original: /etc/nginx/nginx.conf
  └── 20260507_174501_d4e5f6/
      └── old_config.yaml     # original: /opt/app/config.yaml (pre-overwrite backup)
  ```
- **Rationale**: Timestamped directories prevent name collisions. JSON index enables fast lookup and listing. All on remote host so AI can inspect via tools.

### 10. Audit Log Design

- **Choice**: JSON Lines format at `~/.linux_mcp_audit.log` on remote host.
- **Rationale**: Append-only, machine-parseable, human-readable. Each line is one operation record.
- **Record format**: `{"timestamp": "...", "operation": "delete_file", "params": {...}, "result": "success", "exit_code": 0, "rollback_id": "..."}`

### 11. Rollback Strategy: Layered

- **Choice**: Three-tier rollback strategy based on operation type.
- **Tiers**:
  - **Auto-rollback** (file ops): System automatically creates backups before destructive actions. Rollback restores from trash.
  - **Conditional rollback** (command execution): AI must provide `rollback_command`. Dangerous commands without one are rejected.
  - **No rollback** (process kill): Irreversible. Requires explicit `confirm_destructive: true` flag. Audit logged.
- **Rationale**: Balances safety with usability. Doesn't block safe operations. Forces AI to think about reversibility for dangerous ones.

## Risks / Trade-offs

- **SSH connection drops** → Auto-reconnect with retry logic, configurable timeout
- **Large file transfers block event loop** → Stream files in chunks, set size limits (default 10MB)
- **Command injection via shell metacharacters** → Use `asyncssh` process API (no shell by default), document that tools execute as-is
- **Password in environment variable** → Document that SSH key auth is preferred; password auth is available but less secure
- **Single connection bottleneck** → Acceptable for MCP use case (one AI session = one server instance)
- **Trash directory grows unbounded** → Configurable max trash size; `empty_trash` tool for cleanup; warn on large trash
- **Audit log grows unbounded** → Log rotation at configurable size (default 10MB); old logs kept with `.1`, `.2` suffixes
- **Rollback command may be wrong** → Rollback is best-effort; audit log records both original and rollback commands; AI responsible for correctness
- **Race conditions on trash index** → Single SSH connection means serialized access; no concurrent modification risk
