## Context

当前 `key_file` 路径通过 `expand_local_path()` 处理：展开 `~` 和环境变量，然后直接传给 asyncssh。不支持相对路径从工程目录查找。

用户希望密钥文件可以放在 config.json 旁边，方便项目内管理。

## Goals / Non-Goals

**Goals:**
- 相对路径密钥优先从工程目录（config.json 所在目录）查找
- 工程目录找不到时回退到 `~/.ssh/` 目录
- 绝对路径和 `~` 开头路径保持原有行为

**Non-Goals:**
- 不支持多级回退链
- 不支持环境变量中的工程目录

## Decisions

### D1: 工程目录注入 ServerConfig

**选择**: `ServerConfig` 新增 `project_dir: Optional[str]` 字段，`load_config()` 时自动设置

**理由**: `ServerConfig` 负责路径解析，需要知道工程目录。`project_dir` 为 None 时保持旧行为（仅 expand_local_path）。

### D2: 相对路径解析优先级

**选择**: 工程目录 → `~/.ssh/` 目录

```
key_file: "id_rsa"
  1. {project_dir}/id_rsa → 存在则使用
  2. ~/.ssh/id_rsa       → 存在则使用
  3. 都不存在 → 报错
```

**理由**: 工程目录优先，方便项目覆盖用户全局密钥。`~/.ssh/` 作为通用回退。

### D3: 绝对路径和 ~ 路径不变

**选择**: 以 `/`、`\`、盘符、`~` 开头的路径直接走 `expand_local_path()`，不做工程目录查找

**理由**: 这些路径已经是明确的，不需要工程目录介入。
