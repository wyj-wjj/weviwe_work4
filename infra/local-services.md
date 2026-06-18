# 本地 MySQL 与 Milvus 说明

## MySQL

- MySQL 主机：`localhost`
- MySQL 端口：`3306`
- 数据库名：`weview_mvp`
- 推荐版本：MySQL 8.4 LTS
- 本地密钥位置：本机 `.env` 或环境变量，禁止写入仓库文件。

示例数据库 URL 只使用占位值：

```text
mysql+pymysql://weview_user:local_placeholder@localhost:3306/weview_mvp
```

## Milvus

- Milvus 主机：`localhost`
- Milvus 端口：`19530`
- 推荐形态：Milvus Standalone，本地可使用 Docker 启动。
- 角色边界：Milvus 只保存向量索引和过滤元数据，不能作为权威正文来源。

## 启动检查

- 后端健康检查：请求 `GET /health`。
- 前端路由加载：打开 `/login`、`/app`、`/admin`。
- MySQL 连通性：确认 `DATABASE_URL` 能连接到 `weview_mvp`。
- Milvus 连通性：确认 `MILVUS_HOST=localhost` 且 `MILVUS_PORT=19530` 可访问。
