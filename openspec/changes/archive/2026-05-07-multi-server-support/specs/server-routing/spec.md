## ADDED Requirements

### Requirement: 工具 server_name 参数
所有 MCP 工具 SHALL 接受 `server_name` 参数用于指定目标服务器。

#### Scenario: 多服务器模式下指定 server_name
- **WHEN** 配置了多台服务器且工具调用传入了有效的 `server_name`
- **THEN** 系统 SHALL 在对应服务器上执行操作

#### Scenario: 多服务器模式下未传 server_name
- **WHEN** 配置了多台服务器且工具调用未传入 `server_name`
- **THEN** 系统 SHALL 返回错误信息，包含所有可用服务器名称列表，且不执行任何操作

#### Scenario: 多服务器模式下传入不存在的 server_name
- **WHEN** 工具调用传入了不存在的 `server_name`
- **THEN** 系统 SHALL 返回错误信息，包含所有可用服务器名称列表，且不执行任何操作

#### Scenario: 单服务器模式下不传 server_name
- **WHEN** 只配置了一台服务器且工具调用未传入 `server_name`
- **THEN** 系统 SHALL 自动使用唯一的服务器执行操作

#### Scenario: 单服务器模式下传入 server_name
- **WHEN** 只配置了一台服务器且工具调用传入了 `server_name`（匹配唯一服务器名称）
- **THEN** 系统 SHALL 正常执行操作

### Requirement: 动态工具定义
系统 SHALL 根据服务器数量动态生成工具的 inputSchema。

#### Scenario: 单服务器模式下的工具定义
- **WHEN** 只配置了一台服务器
- **THEN** 工具的 inputSchema 中不包含 `server_name` 属性，`required` 列表中不包含 `server_name`

#### Scenario: 多服务器模式下的工具定义
- **WHEN** 配置了多台服务器
- **THEN** 所有工具的 inputSchema 中 SHALL 包含 `server_name` 属性，且 `server_name` SHALL 在 `required` 列表中；工具描述 SHALL 包含必须指定 server_name 的警告

### Requirement: list_servers 工具
系统 SHALL 提供 `list_servers` 工具，列出所有已配置的服务器信息。

#### Scenario: 调用 list_servers
- **WHEN** 用户调用 `list_servers` 工具
- **THEN** 系统 SHALL 返回所有服务器的名称、主机地址、端口、用户名信息

#### Scenario: list_servers 仅多服务器模式可用
- **WHEN** 只配置了一台服务器
- **THEN** `list_servers` 工具 SHALL NOT 出现在工具列表中

### Requirement: 服务器上下文隔离
每台服务器 SHALL 拥有完全独立的 SSH 连接、审计日志、回收站和安全网关实例。

#### Scenario: 独立 SSH 连接
- **WHEN** 对服务器 A 和服务器 B 分别执行操作
- **THEN** 两次操作使用不同的 SSH 连接实例

#### Scenario: 独立审计日志
- **WHEN** 在服务器 A 上执行操作
- **THEN** 审计日志仅记录在服务器 A 的审计日志文件中，不影响服务器 B

#### Scenario: 独立回收站
- **WHEN** 在服务器 A 上删除文件
- **THEN** 文件移入服务器 A 的回收站，不影响服务器 B 的回收站
