## MODIFIED Requirements

### Requirement: 密钥文件路径解析
系统 SHALL 按以下优先级解析 `key_file` 路径：工程目录 → 用户 `.ssh` 目录。

#### Scenario: 相对路径在工程目录找到
- **WHEN** `key_file` 为相对路径（如 `id_rsa`）且工程目录下存在该文件
- **THEN** 系统使用工程目录下的密钥文件

#### Scenario: 相对路径回退到用户目录
- **WHEN** `key_file` 为相对路径且工程目录下不存在
- **THEN** 系统尝试 `~/.ssh/{key_file}` 路径

#### Scenario: 绝对路径不变
- **WHEN** `key_file` 为绝对路径（以 `/` 或盘符开头）
- **THEN** 系统直接使用该路径，不做工程目录查找

#### Scenario: ~ 路径不变
- **WHEN** `key_file` 以 `~` 开头
- **THEN** 系统展开 `~` 后直接使用，不做工程目录查找

#### Scenario: 密钥文件不存在
- **WHEN** 所有查找路径都不存在
- **THEN** 系统返回明确的文件不存在错误
