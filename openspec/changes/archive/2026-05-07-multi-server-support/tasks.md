## 1. 配置模型重构

- [x] 1.1 将 `Config` 类重命名为 `ServerConfig`，新增 `name: str` 必填字段
- [x] 1.2 创建 `AppConfig` 类，包含 `servers: list[ServerConfig]`，实现名称唯一性校验、`is_single_server`、`default_name`、`get_server()`、`server_names` 属性
- [x] 1.3 实现 `defaults` 合并逻辑：server 条目覆盖 defaults 同名字段
- [x] 1.4 实现旧格式自动兼容：检测 `host` 键且无 `servers` 键时自动包装为 `servers: [{name: "default", ...}]`
- [x] 1.5 删除 `load_config_from_env()` 函数和 `env_mapping` 字典
- [x] 1.6 重写 `create_config()` → `load_config(config_path: str) -> AppConfig`，仅从文件加载，删除环境变量覆盖逻辑
- [x] 1.7 更新 `__main__.py`：`--config` 参数改为必填，无配置文件时报错退出

## 2. 全局状态改造

- [x] 2.1 创建 `ServerContext` 数据类，包含 `config: ServerConfig`、`ssh: SSHClient`、`audit: AuditLogger`、`trash: TrashManager`、`safety: SafetyGate`
- [x] 2.2 将全局变量 `_config/_ssh/_audit/_trash/_safety` 替换为 `_app_config: AppConfig` 和 `_contexts: dict[str, ServerContext]`
- [x] 2.3 实现 `get_context(name: str) -> ServerContext` 函数
- [x] 2.4 实现 `resolve_server(server_name: Optional[str]) -> str` 函数：单服务器模式自动返回默认名，多服务器模式验证必填和存在性

## 3. 工具层改造

- [x] 3.1 所有工具处理函数（handle_run_command 等）新增 `server_name: Optional[str] = None` 参数，内部通过 `resolve_server` + `get_context` 获取对应 ServerContext
- [x] 3.2 实现 `list_tools()` 动态生成：单服务器模式不包含 `server_name`，多服务器模式将 `server_name` 加入 properties 和 required，描述加警告
- [x] 3.3 实现 `handle_list_servers` 工具处理函数，返回所有服务器名称、主机、端口、用户名
- [x] 3.4 将 `list_servers` 工具定义加入 `TOOLS` 列表（仅多服务器模式）
- [x] 3.5 更新 `TOOL_HANDLERS` 映射，加入 `list_servers`

## 4. 组件初始化改造

- [x] 4.1 重写 `init_components(config: AppConfig)`：为每个 ServerConfig 创建独立的 ServerContext
- [x] 4.2 重写 `shutdown_components()`：遍历所有 ServerContext 断开 SSH 连接
- [x] 4.3 更新 `run_server()` 适配新的 `load_config()` 返回 `AppConfig`

## 5. 配置示例和文档

- [x] 5.1 重写 `config.example.json` 为新格式（含 defaults + 多 servers 示例）
- [x] 5.2 更新 README.md：删除环境变量说明，更新配置格式说明

## 6. 测试验证

- [x] 6.1 验证旧格式配置文件自动兼容
- [x] 6.2 验证新格式多服务器配置加载
- [x] 6.3 验证多服务器模式下不传 server_name 返回错误
- [x] 6.4 验证多服务器模式下传入错误 server_name 返回错误
- [x] 6.5 验证单服务器模式下不传 server_name 正常工作
- [x] 6.6 验证 list_servers 工具输出
- [x] 6.7 验证各服务器上下文隔离（独立连接、审计、回收站）
