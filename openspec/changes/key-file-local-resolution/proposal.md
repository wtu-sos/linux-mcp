## Why

当前 `key_file` 路径解析仅支持绝对路径和 `~` 展开。用户希望将密钥文件放在工程目录（config.json 旁边），方便项目管理和分发。需要支持相对路径优先从工程目录查找，找不到再回退到用户目录。

## What Changes

- `ServerConfig.key_file_expanded` 改为 `key_file_resolved`，接受工程目录参数
- 相对路径解析优先级：工程目录 → 用户 `~/.ssh/` 目录
- 绝对路径和 `~` 开头路径保持原有行为
- `load_config()` 将配置文件所在目录注入 `ServerConfig`
- `SSHClient.connect()` 适配新的解析方法

## Capabilities

### Modified Capabilities
- `ssh-connection`: 密钥文件路径解析逻辑变更

## Impact

- `config.py`: `ServerConfig` 新增 `project_dir` 字段，`key_file_expanded` → `key_file_resolved`
- `ssh_client.py`: `connect()` 中 `key_file_expanded` → `key_file_resolved`
- `server.py`: `init_components()` 传入工程目录
