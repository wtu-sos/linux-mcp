## Why

当前配置只支持单个 SSH 服务器连接，配置是扁平结构且没有服务器名称标识。用户无法在同一个 MCP 服务器实例中管理多台远程主机，也无法在工具调用时指定目标服务器。此外，环境变量配置方式与多服务器场景不兼容，增加了不必要的复杂度。

## What Changes

- **BREAKING**: 配置格式从扁平结构改为 `servers` 数组 + `defaults` 共享默认值
- **BREAKING**: 删除环境变量配置支持（`SSH_HOST`, `SSH_USER` 等），仅支持配置文件
- **BREAKING**: 所有 MCP 工具新增 `server_name` 参数，多服务器模式下为必填
- 新增 `list_servers` 工具，列出所有已配置的服务器
- 旧格式（扁平 JSON）自动兼容，包装为单服务器配置
- 单服务器模式下 `server_name` 参数可选，保持向后兼容
- 多服务器模式下不传 `server_name` 返回错误（列出可用服务器名称）
- 全局状态从单例改为按服务器名称索引的字典

## Capabilities

### New Capabilities
- `multi-server-config`: 多服务器配置加载、defaults 合并、旧格式兼容、名称唯一性校验
- `server-routing`: 工具调用时的服务器路由、server_name 验证、错误提示

### Modified Capabilities
- `ssh-connection`: 配置加载方式变更（删除环境变量，改用 servers 数组），连接管理从单例改为多实例

## Impact

- **config.py**: 大幅重构，`Config` → `ServerConfig` + `AppConfig`，删除环境变量加载逻辑
- **server.py**: 大幅重构，全局状态改为字典索引，所有工具加 `server_name` 参数，动态 `required`，新增 `list_servers`
- **ssh_client.py**: 无需改动（依赖 Config 接口不变）
- **audit.py / trash.py / safety.py**: 小幅调整构造函数参数
- **config.example.json**: 重写为新格式示例
- **文档**: 删除环境变量相关说明，更新配置示例
