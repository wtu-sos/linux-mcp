## Context

当前 `CommandClassifier.classify()` 将所有危险命令归为一类。`rm` 在 `DANGEROUS_COMMANDS` 中，只要有回滚命令就放行。但 `rm` 应该走 `delete_file` 工具（回收站），不应通过 `run_command` 直接执行。

## Goals / Non-Goals

**Goals:**
- `rm`/`rmdir`/`unlink` 在 `run_command` 中直接拒绝
- 拒绝时提示使用 `delete_file` 工具
- 回滚命令验证增强：拒绝 trivial 回滚命令

**Non-Goals:**
- 不改变其他危险命令的行为
- 不改变 `delete_file` 工具

## Decisions

### D1: 新增 BLOCKED_COMMANDS 列表

**选择**: 新增 `BLOCKED_COMMANDS` 列表，包含 `rm`, `rmdir`, `unlink`

**理由**: 这些命令应通过 `delete_file` 工具执行（走回收站），不应在 `run_command` 中直接执行。

### D2: 回滚命令验证增强

**选择**: 拒绝以下 trivial 回滚命令：
- 空字符串
- 仅包含 `echo`、`true`、`:` 等无操作命令
- 与原始命令相同（循环）

**理由**: 防止 AI 用假回滚命令绕过安全检查。
