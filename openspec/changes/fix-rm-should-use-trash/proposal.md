## Why

两个安全问题：

1. **`rm` 命令绕过回收站**：`run_command` 执行 `rm` 时，只要提供了回滚命令就放行。但回滚命令可能是假的（如 `echo 'read-only'`），导致文件被永久删除而非移入回收站。
2. **回滚命令验证太弱**：`pre_check_command` 只检查回滚命令是否存在，不验证其是否能真正撤销操作。

## What Changes

- `rm` 相关命令（`rm`, `rmdir`, `unlink`）从 `DANGEROUS_COMMANDS` 移至新的 `BLOCKED_COMMANDS` 列表
- `BLOCKED_COMMANDS` 中的命令在 `run_command` 中直接拒绝，提示使用 `delete_file` 工具
- 回滚命令验证增强：检查回滚命令是否与原始命令相关（非空、非 trivial）

## Capabilities

### Modified Capabilities
- `command-execution`: 命令分类逻辑变更，新增 BLOCKED_COMMANDS

## Impact

- `safety.py`: 新增 `BLOCKED_COMMANDS`，修改 `classify()` 和 `pre_check_command()`
- `server.py`: `handle_run_command` 适配新的拒绝消息
