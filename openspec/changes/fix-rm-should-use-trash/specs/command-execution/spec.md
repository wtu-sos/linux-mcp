## MODIFIED Requirements

### Requirement: 命令分类
系统 SHALL 将 `rm`、`rmdir`、`unlink` 归类为 blocked 命令，在 `run_command` 中直接拒绝。

#### Scenario: rm 命令被拒绝
- **WHEN** 用户通过 `run_command` 执行 `rm` 命令
- **THEN** 系统 SHALL 拒绝执行，并提示使用 `delete_file` 工具

#### Scenario: rmdir 命令被拒绝
- **WHEN** 用户通过 `run_command` 执行 `rmdir` 命令
- **THEN** 系统 SHALL 拒绝执行，并提示使用 `delete_file` 工具

#### Scenario: 其他危险命令仍需要回滚命令
- **WHEN** 用户通过 `run_command` 执行 `mv`、`dd` 等危险命令
- **THEN** 系统 SHALL 要求提供回滚命令

### Requirement: 回滚命令验证
系统 SHALL 验证回滚命令的有效性，拒绝 trivial 回滚命令。

#### Scenario: 拒绝空回滚命令
- **WHEN** 回滚命令为空字符串
- **THEN** 系统 SHALL 拒绝并提示提供有效的回滚命令

#### Scenario: 拒绝无操作回滚命令
- **WHEN** 回滚命令仅为 `echo`、`true`、`:` 等无操作命令
- **THEN** 系统 SHALL 拒绝并提示提供有效的回滚命令
