## 1. 安全层修复

- [x] 1.1 `safety.py` 新增 `BLOCKED_COMMANDS` 列表（`rm`, `rmdir`, `unlink`），从 `DANGEROUS_COMMANDS` 中移除
- [x] 1.2 `CommandClassifier.classify()` 新增 `blocked` 分类
- [x] 1.3 `SafetyGate.pre_check_command()` 处理 `blocked` 分类，返回拒绝消息（提示使用 `delete_file`）
- [x] 1.4 回滚命令验证增强：拒绝空字符串和 trivial 命令（`echo`, `true`, `:`）

## 2. 测试验证

- [x] 2.1 验证 `rm` 命令被拒绝
- [x] 2.2 验证 `rmdir` 命令被拒绝
- [x] 2.3 验证 trivial 回滚命令被拒绝
- [x] 2.4 验证其他危险命令仍正常工作
