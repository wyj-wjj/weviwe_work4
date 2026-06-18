# 本地开发启动说明

本文档适用于 Windows PowerShell。命令默认从仓库根目录 `E:\WeView\work4` 执行。

## 1. 运行依赖

- Python 3.12 或 3.13。
- Node.js 24 LTS、Corepack、pnpm。
- MySQL 8.4 LTS。
- Milvus Standalone，默认监听 `127.0.0.1:19530`。
- 真实 AI 联调需要有效的 DashScope API Key。

## 2. 配置根目录 `.env`

复制 `.env.example` 为 `.env`，只在本机填写真实值，不得提交：

```dotenv
DATABASE_URL=mysql+pymysql://<mysql-user>:<url-encoded-password>@127.0.0.1:3306/weview_mvp
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=weview_content_chunks_real_v4
DASHSCOPE_API_KEY=<local-secret>
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=qwen-plus
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
RAG_SIMILARITY_THRESHOLD=0.7
RAG_TOP_K=5
JWT_SECRET_KEY=<至少32位随机字符串>
USE_FAKE_EXTERNAL_CLIENTS=false
```

说明：

- MySQL 密码包含 `@`、`:`、`/`、`%` 等字符时必须 URL 编码。
- 真实联调必须设置 `USE_FAKE_EXTERNAL_CLIENTS=false`。
- 已有 Milvus collection 如果使用过不同向量维度，应改用新的 `MILVUS_COLLECTION_NAME`。
- 自动化测试不读取真实 DashScope Key。

## 3. 安装依赖

```powershell
cd E:\WeView\work4
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"

cd frontend
corepack.cmd pnpm install
corepack.cmd pnpm exec playwright install chromium
cd ..
```

## 4. 启动 MySQL 和 Milvus

MySQL 可以使用本机服务或 Docker。数据库至少需要：

```sql
CREATE DATABASE IF NOT EXISTS weview_mvp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
```

Milvus 使用官方 Standalone Docker Compose 启动，确保：

- `MILVUS_HOST=127.0.0.1`
- `MILVUS_PORT=19530`
- 容器健康且 19530 端口可访问

检查端口：

```powershell
Test-NetConnection 127.0.0.1 -Port 3306
Test-NetConnection 127.0.0.1 -Port 19530
```

## 5. 执行数据库迁移

根目录 `.env` 已配置后：

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m alembic upgrade head
cd ..
```

Alembic 在默认 URL 仍为占位值时会读取根目录 `.env` 的 `DATABASE_URL`。测试代码显式传入的数据库 URL 不会被覆盖。

## 6. 创建首个管理员

首个管理员是唯一允许通过运维命令直接写入 MySQL 的启动数据：

```powershell
cd E:\WeView\work4
$env:PYTHONPATH='backend'
$env:INITIAL_ADMIN_USERNAME='local_admin'
$env:INITIAL_ADMIN_DISPLAY_NAME='本地系统管理员'
$env:INITIAL_ADMIN_PASSWORD='<至少8位的本地密码>'
.\.venv\Scripts\python.exe -m app.cli.create_admin
Remove-Item Env:INITIAL_ADMIN_PASSWORD
```

员工账号、内容、测验和未命中问题应通过前端和 FastAPI 创建，不使用直写数据库脚本。

## 7. 启动后端

新 PowerShell 窗口：

```powershell
cd E:\WeView\work4
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期返回 `status=ok` 和 `service=weview-work4-api`。

## 8. 配置并启动前端

在 `frontend/.env.local` 写入：

```dotenv
VITE_API_BASE_URL=/api
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

新 PowerShell 窗口：

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm dev
```

打开 `http://127.0.0.1:5173/login`。

## 9. 测试命令

后端测试：

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest
```

前端单元/组件测试：

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm test:unit
```

前端生产构建：

```powershell
corepack.cmd pnpm build
```

Playwright 冒烟测试：

```powershell
corepack.cmd pnpm test:e2e
```

Playwright 会自行启动阶段 10 专用 SQLite 后端与 Vite，不连接真实 MySQL、Milvus 或 DashScope。真实链路验收见 `docs/frontend-testing-manual.md`。
