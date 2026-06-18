# 宝塔与阿里云 ECS 部署说明

## 1. 部署拓扑

```text
浏览器
  -> Nginx / 宝塔网站
    -> 前端 dist：静态 HTML、CSS、JavaScript
    -> /api：反向代理到 127.0.0.1:8000
      -> FastAPI
        -> MySQL
        -> Milvus Standalone
        -> DashScope
```

前端是静态 HTML 项目，生产环境不需要 Node.js 常驻服务器。Node.js 只用于安装依赖和执行 `pnpm build`。

## 2. ECS 基础准备

- 推荐 Linux ECS。
- 安全组只开放 80/443 和必要的 SSH 管理端口。
- FastAPI 端口、MySQL 端口和 Milvus 端口默认不对公网开放。
- 使用独立系统用户运行后端，不用 root 常驻运行应用。
- `.env` 只保存在服务器，权限限制为应用用户可读。

## 3. MySQL

MySQL 是唯一业务数据库，保存账号、内容、版本、chunk、测验、未命中问题和索引审计记录。

SQLAlchemy 不是数据库，它只是 FastAPI 访问 MySQL 的 ORM。不要额外部署所谓“SQLAlchemy 数据库”。

可选方案：

- MVP：ECS 本机 MySQL 8.4。
- 正式环境：阿里云 RDS MySQL 8.4。

无论采用哪一种，先创建 UTF-8 数据库，再配置 `DATABASE_URL` 并执行：

```bash
cd /www/wwwroot/weview/backend
/www/wwwroot/weview/.venv/bin/python -m alembic upgrade head
```

## 4. Milvus

Milvus 是主要额外运行时服务，只保存向量和过滤元数据，不保存权威正文。

- 推荐通过 Docker 运行 Milvus Standalone。
- 仅允许 FastAPI 所在主机或内网访问 19530。
- 持久化挂载 Milvus、etcd、对象存储相关数据目录。
- 升级 embedding 模型或向量维度时使用新 collection，并重新发布/重建索引。

## 5. 后端 Python 项目

安装：

```bash
cd /www/wwwroot/weview
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e './backend'
```

后端监听本机地址：

```bash
/www/wwwroot/weview/.venv/bin/python -m uvicorn app.main:app \
  --app-dir /www/wwwroot/weview/backend \
  --host 127.0.0.1 \
  --port 8000
```

生产环境建议由 systemd、Supervisor 或宝塔 Python 项目管理器托管，并配置自动重启和日志轮转。

## 6. 前端静态项目

构建：

```bash
cd /www/wwwroot/weview/frontend
corepack pnpm install --frozen-lockfile
VITE_API_BASE_URL=/api corepack pnpm build
```

宝塔网站根目录指向：

```text
/www/wwwroot/weview/frontend/dist
```

Vue Router 使用 history 模式，Nginx 必须把前端路由回退到 `index.html`。

## 7. Nginx / 宝塔反向代理

核心配置：

```nginx
location / {
    try_files $uri $uri/ /index.html;
}

location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

FastAPI 只监听 `127.0.0.1`，位于 Nginx 或宝塔反向代理之后。

## 8. DashScope

服务器 `.env` 配置：

```dotenv
USE_FAKE_EXTERNAL_CLIENTS=false
DASHSCOPE_API_KEY=<server-secret>
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=qwen-plus
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
```

DashScope 是后端调用的外部 API。前端不得直接调用 DashScope，也不得把 `DASHSCOPE_API_KEY` 编译进静态资源。

## 9. 上线检查

- `GET /health` 返回成功。
- Alembic 已升级到 `head`。
- 管理员可以登录。
- 发布内容后 MySQL 生成版本和 chunk。
- 索引状态变为 `synced`，Milvus 中出现对应向量。
- 通用权限账号看不到全量内容。
- AI 命中返回来源，未命中写入后台列表。
- HTTPS、数据库备份、Milvus 数据持久化和日志轮转已配置。
