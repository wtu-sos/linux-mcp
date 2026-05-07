## ADDED Requirements

### Requirement: 多服务器配置格式
系统 SHALL 支持在 JSON 配置文件中使用 `servers` 数组定义多台服务器，每个服务器条目 MUST 包含唯一的 `name` 字段。

#### Scenario: 标准多服务器配置
- **WHEN** 配置文件包含 `servers` 数组和 `defaults` 对象
- **THEN** 系统为每个 server 条目合并 defaults 值，server 条目中的字段覆盖 defaults 中的同名字段

#### Scenario: 服务器名称唯一性
- **WHEN** 配置文件中存在两个 name 相同的服务器条目
- **THEN** 系统 SHALL 拒绝加载并返回明确的错误信息，指出重复的名称

#### Scenario: 空服务器列表
- **WHEN** 配置文件中 `servers` 数组为空
- **THEN** 系统 SHALL 拒绝加载并返回错误信息

### Requirement: defaults 共享默认值
系统 SHALL 支持 `defaults` 对象为所有服务器提供共享默认值，服务器条目中的字段 MUST 优先于 defaults。

#### Scenario: defaults 被服务器条目覆盖
- **WHEN** defaults 中定义 `timeout: 30`，某服务器条目定义 `timeout: 60`
- **THEN** 该服务器使用 `timeout: 60`，其他服务器使用 `timeout: 30`

#### Scenario: 无 defaults 对象
- **WHEN** 配置文件中没有 `defaults` 对象
- **THEN** 所有服务器使用 ServerConfig 中定义的内置默认值

### Requirement: 旧格式自动兼容
系统 SHALL 自动检测并兼容旧版扁平配置格式。

#### Scenario: 旧格式自动包装
- **WHEN** 配置文件包含 `host` 键且不包含 `servers` 键
- **THEN** 系统自动将其包装为 `servers: [{name: "default", ...原配置}]`

#### Scenario: 旧格式下单服务器模式
- **WHEN** 使用旧格式配置（自动包装后只有一个服务器）
- **THEN** 系统进入单服务器模式，`server_name` 参数可选

### Requirement: 删除环境变量配置
系统 SHALL NOT 支持通过环境变量配置服务器连接参数。

#### Scenario: 忽略环境变量
- **WHEN** 设置了 `SSH_HOST`、`SSH_USER` 等环境变量
- **THEN** 系统 SHALL 忽略这些环境变量，仅从配置文件加载

### Requirement: 配置文件路径参数
系统 SHALL 通过命令行 `--config` / `-c` 参数指定配置文件路径。

#### Scenario: 指定配置文件
- **WHEN** 启动时传入 `--config /path/to/config.json`
- **THEN** 系统从指定路径加载配置文件

#### Scenario: 未指定配置文件
- **WHEN** 启动时未传入 `--config` 参数
- **THEN** 系统 SHALL 报错并退出，提示需要配置文件
