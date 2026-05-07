## Context

当前 linux-ssh-mcp 仅支持单台 SSH 服务器连接。配置为扁平 JSON 结构，无服务器名称标识，全局状态为单例模式（`_ssh`, `_audit`, `_trash`, `_safety`）。所有工具函数通过 `get_ssh()` 获取唯一的 SSH 客户端。配置支持 JSON 文件和环境变量两种来源。

用户需要在同一 MCP 实例中管理多台远程主机，当前架构无法实现。

## Goals / Non-Goals

**Goals:**
- 支持配置文件中定义多台 SSH 服务器，每台有唯一名称
- 工具调用时可指定目标服务器（`server_name` 参数）
- 多服务器模式下 `server_name` 必填，不传则返回错误并列出可用服务器
- 单服务器模式下 `server_name` 可选，保持向后兼容
- 旧格式（扁平 JSON）自动兼容
- 删除环境变量配置支持，简化配置来源

**Non-Goals:**
- 不支持服务器分组/标签
- 不支持动态添加/删除服务器（需重启才能生效）
- 不支持连接池或连接复用优化
- 不支持跨服务器操作（如服务器间文件传输）
- 不实现服务器健康检查或自动重连监控

## Decisions

### D1: 配置格式 — 顶层 servers 数组 + defaults

**选择**: `servers` 数组 + `defaults` 共享默认值

```json
{
  "defaults": { "port": 22, "timeout": 30, ... },
  "servers": [
    { "name": "prod-web1", "host": "10.0.1.1", "username": "root" },
    { "name": "staging", "host": "10.0.3.1", "username": "deploy", "timeout": 60 }
  ]
}
```

**备选方案**:
- 字典格式 `servers: { "name": {...} }`: 字典键与 name 字段冗余
- 纯数组无 defaults: 重复配置多，体验差

**理由**: 数组保持顺序和唯一性约束明确；defaults 减少重复；server 条目覆盖 defaults 的字段。

### D2: 工具层 — 每个工具加 server_name 参数

**选择**: 所有工具加 `server_name` 参数，多服务器时必填

**备选方案**:
- `switch_server` 工具 + 会话状态: 有状态，AI 易忘记切换，并发混乱
- MCP 多实例: 工具名爆炸（20工具 × N服务器），配置冗长
- `server_name` 可选 + 默认服务器: AI 可能操作错误服务器，生产环境危险

**理由**: 显式传参最安全，AI 每次调用都明确目标。多服务器时必填避免误操作。

### D3: 旧格式兼容 — 自动包装

**选择**: 检测到 `host` 键且无 `servers` 键时，自动包装为 `servers: [{name: "default", ...原配置}]`

**理由**: 零迁移成本，旧配置文件无需修改即可使用。

### D4: 删除环境变量支持

**选择**: 完全删除 `load_config_from_env()` 和所有环境变量映射

**理由**: 环境变量是扁平的，无法表达多服务器；保留会制造两种配置路径的混乱；配置文件是唯一合理的多服务器配置方式。

### D5: 全局状态 — 按名称索引的 ServerContext 字典

**选择**: `dict[str, ServerContext]`，每个 ServerContext 包含独立的 config/ssh/audit/trash/safety

```python
class ServerContext:
    config: ServerConfig
    ssh: SSHClient
    audit: AuditLogger
    trash: TrashManager
    safety: SafetyGate
```

**理由**: 完全隔离，每台服务器有独立的连接、审计日志、回收站。无共享状态，无并发问题。

### D6: 动态工具定义

**选择**: `list_tools()` 根据服务器数量动态生成工具 schema

- 单服务器: 工具签名不变，不出现 `server_name`
- 多服务器: 所有工具加 `server_name` 到 properties 和 required，描述加警告

**理由**: 单服务器用户体验零变化；多服务器时强制传参。

### D7: 连接策略 — 懒连接

**选择**: 保持现有懒连接行为，每台服务器首次调用时才建立连接

**理由**: 启动快；某台不可用不影响其他服务器；无需预连接健康检查。

## Risks / Trade-offs

- **[Breaking Change]** 删除环境变量支持 → 迁移指南：改用配置文件
- **[Breaking Change]** 多服务器模式下工具签名变化 → AI 需要适应新参数，`list_servers` 工具辅助
- **[AI 遗漏 server_name]** AI 可能忽略 server_name 参数 → 多服务器时设为必填 + 错误信息列出可用服务器
- **[配置文件格式变更]** 旧格式用户可能困惑 → 自动兼容 + 文档说明
- **[内存占用]** 多台服务器同时保持连接 → 懒连接缓解，按需建立
