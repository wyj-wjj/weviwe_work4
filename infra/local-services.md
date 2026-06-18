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
- 真实 `text-embedding-v4` 当前返回 1024 维向量；不要复用由 3 维假向量创建的 collection。
- 本地真实联调建议使用独立名称，例如 `weview_content_chunks_real_v4`。

## DashScope

- 真实联调设置 `USE_FAKE_EXTERNAL_CLIENTS=false`。
- 北京地域 base URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`。
- 生成模型：`qwen-plus`。
- Embedding：`text-embedding-v4`。
- API Key 只放在根目录 `.env` 或服务器环境变量，前端不得读取。

## 启动检查

- 后端健康检查：请求 `GET /health`。
- 前端路由加载：打开 `/login`、`/app`、`/admin`。
- MySQL 连通性：确认 `DATABASE_URL` 能连接到 `weview_mvp`。
- Milvus 连通性：确认 `MILVUS_HOST=localhost` 且 `MILVUS_PORT=19530` 可访问。
- DashScope 连通性：由后端调用 embedding/chat；自动化测试继续使用假客户端。
