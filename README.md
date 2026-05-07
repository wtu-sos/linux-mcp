# Linux SSH MCP Server

AI 驱动的远程 Linux 管理 MCP 服务器，通过 SSH 连接让 AI 助手安全地操作远程 Linux 机器。

## 功能

- **命令执行**：在远程主机上执行 Shell 命令，支持危险命令分类和回滚
- **文件操作**：读写、列表、删除（回收站）、上传、下载文件
- **进程管理**：列出和终止进程（需确认）
- **系统信息**：获取 CPU、内存、磁盘、操作系统和运行时间
- **安全层**：审计日志、回收站、操作回滚
- **多服务器支持**：同一实例管理多台远程主机

## 环境要求

- Python 3.10+
- 远程 Linux 主机（支持 SSH 连接）
- SSH 密钥或密码认证

## 安装

### 从源码安装（推荐）

```bash
git clone https://github.com/linux-ssh-mcp/linux-ssh-mcp.git
cd linux-ssh-mcp
pip install -e .
```

### 从 PyPI 安装

```bash
pip install linux-ssh-mcp
```

### 验证安装

```bash
linux-ssh-mcp --help
```

## 快速开始

### 1. 准备 SSH 连接

确保可以 SSH 连接到远程 Linux 主机：

```bash
ssh user@your-server.com
```

推荐使用 SSH 密钥认证：

```bash
ssh-copy-id user@your-server.com
```

### 2. 配置

创建 `config.json`：

**单服务器（旧格式，自动兼容）：**

```json
{
    "host": "192.168.1.100",
    "port": 22,
    "username": "root",
    "key_file": "~/.ssh/id_rsa",
    "timeout": 30
}
```

**多服务器（新格式）：**

```json
{
    "defaults": {
        "port": 22,
        "timeout": 30,
        "command_timeout": 60
    },
    "servers": [
        {
            "name": "prod-web1",
            "host": "192.168.1.100",
            "username": "root",
            "key_file": "~/.ssh/id_rsa"
        },
        {
            "name": "staging",
            "host": "10.0.3.1",
            "port": 2222,
            "username": "deploy",
            "key_file": "~/.ssh/staging_key",
            "timeout": 60
        }
    ]
}
```

`defaults` 中的值会被 server 条目中的同名字段覆盖。

### 3. 运行

```bash
# 使用配置文件（必填）
linux-ssh-mcp --config /path/to/config.json

# 作为 Python 模块
python -m linux_ssh_mcp --config /path/to/config.json
```

## 接入 AI 客户端

### Claude Desktop

编辑 Claude Desktop 的 MCP 配置文件：

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
    "mcpServers": {
        "linux-ssh": {
            "command": "linux-ssh-mcp",
            "args": ["--config", "/path/to/config.json"]
        }
    }
}
```

重启 Claude Desktop 后即可使用。

### Cursor

编辑 Cursor 的 MCP 配置文件（`.cursor/mcp.json`）：

```json
{
    "mcpServers": {
        "linux-ssh": {
            "command": "linux-ssh-mcp",
            "args": ["--config", "/path/to/config.json"]
        }
    }
}
```

## 完整配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| name | - | 服务器名称，多服务器模式下用于工具调用时指定目标 |
| host | - | 远程主机地址（必填） |
| port | 22 | SSH 端口 |
| username | - | SSH 用户名（必填） |
| password | - | SSH 密码（不推荐） |
| key_file | - | SSH 私钥路径 |
| timeout | 30 | 连接超时（秒） |
| command_timeout | 60 | 命令执行超时（秒） |
| max_output_size | 1048576 | 命令输出最大大小（字节，默认 1MB） |
| max_read_size | 10485760 | 文件读取最大大小（字节，默认 10MB） |
| max_upload_size | 10485760 | 文件上传最大大小（字节，默认 10MB） |
| trash_dir | ~/.linux_mcp_trash | 回收站目录（远程主机上） |
| audit_log_path | ~/.linux_mcp_audit.log | 审计日志路径（远程主机上） |
| max_trash_size | 104857600 | 回收站警告阈值（字节，默认 100MB） |
| max_audit_size | 10485760 | 审计日志轮转大小（字节，默认 10MB） |
| max_processes | 200 | 进程列表最大返回数量 |

## MCP 工具列表

### 命令执行
| 工具 | 说明 |
|------|------|
| `run_command` | 执行 Shell 命令，危险命令需提供回滚命令 |

### 文件操作
| 工具 | 说明 |
|------|------|
| `read_file` | 读取远程文件内容 |
| `write_file` | 写入远程文件（覆盖前自动备份旧版本） |
| `list_directory` | 列出目录内容 |
| `delete_file` | 删除文件（移入回收站，可恢复） |
| `upload_file` | 上传本地文件到远程主机 |
| `download_file` | 从远程主机下载文件到本地 |

### 进程管理
| 工具 | 说明 |
|------|------|
| `list_processes` | 列出运行中的进程 |
| `kill_process` | 按 PID 终止进程（需确认） |
| `kill_process_by_name` | 按名称终止进程（需确认） |

### 系统信息
| 工具 | 说明 |
|------|------|
| `get_system_info` | 获取完整系统信息 |
| `get_cpu_info` | 获取 CPU 信息 |
| `get_memory_info` | 获取内存信息 |
| `get_disk_info` | 获取磁盘信息 |
| `get_os_info` | 获取操作系统信息 |
| `get_uptime` | 获取运行时间 |

### 安全管理
| 工具 | 说明 |
|------|------|
| `get_audit_log` | 查看审计日志，支持按操作类型和时间过滤 |
| `list_trash` | 列出回收站内容 |
| `restore_file` | 从回收站恢复文件 |
| `empty_trash` | 清空回收站（需确认） |
| `rollback_operation` | 回滚指定操作（通过审计日志条目 ID） |

### 多服务器管理
| 工具 | 说明 |
|------|------|
| `list_servers` | 列出所有已配置的服务器（仅多服务器模式） |

## 多服务器使用

配置多台服务器后，所有工具都需要指定 `server_name` 参数：

```
AI: 查看 prod-web1 的系统信息
→ 调用 get_system_info(server_name="prod-web1")

AI: 查看 staging 的磁盘
→ 调用 get_disk_info(server_name="staging")
```

不传 `server_name` 会返回错误并列出可用服务器名称。使用 `list_servers` 查看所有可用服务器。

单服务器模式下 `server_name` 参数可选，保持向后兼容。

## 安全特性

### 审计日志

所有操作自动记录到远程主机上的 `~/.linux_mcp_audit.log`（JSON Lines 格式）：

```json
{"id": "20260507_173000_123456", "timestamp": "2026-05-07T09:30:00+00:00", "operation": "run_command", "params": {"command": "ls -la"}, "result": "success", "exit_code": 0}
```

可通过 `get_audit_log` 工具查看。

### 回收站

删除的文件不会永久删除，而是移入 `~/.linux_mcp_trash/`：

```
~/.linux_mcp_trash/
├── .index.json                    # 回收站索引
├── 20260507_173000_a1b2c3/
│   └── deleted_file.conf         # 原始路径: /etc/deleted_file.conf
└── 20260507_173100_d4e5f6/
    └── old_config.yaml           # write_file 覆盖前的旧版本
```

可通过 `list_trash` 查看，`restore_file` 恢复，`empty_trash` 清空。

### 命令分类

| 分类 | 说明 | 行为 |
|------|------|------|
| 安全命令 | `ls`, `cat`, `grep`, `ps`, `df` 等只读命令 | 直接执行 |
| 危险命令 | `rm`, `mv`, `dd`, `apt`, `systemctl` 等 | 需提供 `rollback_command` |
| 不可逆操作 | `kill_process`, `kill_process_by_name` | 需 `confirm_destructive=true` |

### 路径风险感知

操作高风险路径（`/etc/`, `/boot/`, `/usr/` 等）时，即使命令本身是安全的，也会升级为危险等级。

### 操作回滚

- **文件操作**：自动从回收站恢复
- **命令执行**：执行 AI 提供的回滚命令
- **不可逆操作**：拒绝回滚

## 使用示例

### 示例 1：查看系统状态

```
AI: 帮我看看服务器状态
→ 调用 get_system_info
→ 返回 CPU、内存、磁盘、OS、运行时间
```

### 示例 2：安全地修改配置文件

```
AI: 修改 /etc/nginx/nginx.conf
→ 调用 write_file(path="/etc/nginx/nginx.conf", content="...")
→ 系统自动备份旧版本到回收站
→ 写入新内容
→ 如果出问题，可以用 rollback_operation 恢复
```

### 示例 3：执行危险命令

```
AI: 安装 nginx
→ 调用 run_command(
    command="apt install -y nginx",
    rollback_command="apt remove -y nginx"
  )
→ 系统检查：危险命令，有回滚命令 → 允许执行
→ 如果出问题，可以用 rollback_operation 回滚
```

### 示例 4：终止进程

```
AI: 重启 nginx
→ 调用 kill_process_by_name(
    name="nginx",
    confirm_destructive=true
  )
→ 系统检查：不可逆操作，已确认 → 允许执行
```

## 日志级别

通过 `--log-level` 参数控制：

```bash
linux-ssh-mcp --config config.json --log-level DEBUG
```

可选级别：`DEBUG`, `INFO`, `WARNING`, `ERROR`（默认 `INFO`）。

日志输出到 stderr，不会干扰 MCP 的 stdio 通信。

## 常见问题

### Q: 连接失败怎么办？

检查：
1. 远程主机是否可达：`ping your-server.com`
2. SSH 端口是否正确：`ssh -p 22 user@host`
3. 密钥权限是否正确：`chmod 600 ~/.ssh/id_rsa`
4. 查看日志：`linux-ssh-mcp --log-level DEBUG`

### Q: 回收站满了怎么办？

使用 `empty_trash` 工具清空（需要 `confirm_destructive=true`）：

```
AI: 调用 empty_trash(confirm_destructive=true)
```

### Q: 如何查看操作历史？

使用 `get_audit_log` 工具：

```
AI: 调用 get_audit_log(limit=20)
→ 返回最近 20 条操作记录
```

### Q: 支持多台远程主机吗？

支持。使用新格式配置文件（`servers` 数组），同一 MCP 实例可管理多台主机。工具调用时通过 `server_name` 参数指定目标服务器。

## 开发

```bash
# 克隆仓库
git clone https://github.com/linux-ssh-mcp/linux-ssh-mcp.git
cd linux-ssh-mcp

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

## 许可证

MIT
