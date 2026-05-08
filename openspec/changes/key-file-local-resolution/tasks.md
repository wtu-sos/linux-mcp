## 1. 配置模型改造

- [x] 1.1 `ServerConfig` 新增 `project_dir: Optional[str]` 字段，默认 None
- [x] 1.2 `key_file_expanded` 属性改为 `key_file_resolved` 方法，实现工程目录优先查找逻辑
- [x] 1.3 `load_config()` 自动设置每个 `ServerConfig` 的 `project_dir` 为配置文件所在目录

## 2. SSH 客户端适配

- [x] 2.1 `SSHClient.connect()` 中 `key_file_expanded` 改为 `key_file_resolved`

## 3. 测试验证

- [x] 3.1 验证相对路径在工程目录找到密钥
- [x] 3.2 验证相对路径回退到 `~/.ssh/`
- [x] 3.3 验证绝对路径不受影响
- [x] 3.4 验证 `~` 路径不受影响
- [x] 3.5 验证密钥文件不存在时报错
