## MODIFIED Requirements

### Requirement: 配置加载
系统必须从 JSON 配置文件加载配置，支持多服务器配置格式和旧格式自动兼容。

#### Scenario: 从新格式配置文件加载
- **WHEN** 配置路径下存在有效的 JSON 配置文件，包含 `servers` 数组
- **THEN** 系统从文件中读取所有服务器配置，合并 defaults，验证名称唯一性

#### Scenario: 从旧格式配置文件加载
- **WHEN** 配置路径下存在旧格式 JSON 配置文件（包含 `host` 键，不包含 `servers` 键）
- **THEN** 系统自动包装为单服务器配置，name 为 "default"

#### Scenario: 缺少必要配置
- **WHEN** 某个服务器条目缺少必要配置（host、username）
- **THEN** 系统报告缺少哪些必要字段并以明确错误退出

## REMOVED Requirements

### Requirement: 环境变量覆盖
**Reason**: 多服务器配置无法通过扁平环境变量表达，删除以简化配置来源
**Migration**: 使用 JSON 配置文件替代，通过 `--config` 参数指定路径
