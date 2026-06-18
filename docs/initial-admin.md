# 初始管理员账号说明

首个管理员账号只能通过运维命令或环境变量创建，不得在仓库保存真实密码。

建议本地初始化时提供：

```text
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=<operator-provided>
INITIAL_ADMIN_DISPLAY_NAME=系统管理员
```

操作要求：

- `INITIAL_ADMIN_PASSWORD` 必须来自环境变量或一次性运维输入。
- 不要提交 `.env`、截图、日志或任何包含密码的文件。
- 创建账号时后端必须先对密码做哈希，再写入 `users.password_hash`。
