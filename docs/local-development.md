# 本地开发启动说明

## 环境文件

从 `.env.example` 复制本地 `.env`，把本地密钥放在 `.env` 或本机环境变量中，不提交到仓库。

关键配置：

- MySQL 主机：`localhost`
- 数据库名：`weview_mvp`
- Milvus 主机：`localhost`
- Milvus 端口：`19530`
- 本地密钥：`JWT_SECRET_KEY` 和 `DASHSCOPE_API_KEY` 只放在本地 `.env` 或环境变量。

## 后端

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .\backend[dev]
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

后端健康检查：

```powershell
Invoke-RestMethod http://localhost:8000/health
```

预期返回 `status=ok` 和 `service=weview-work4-api`。

## 前端

```powershell
cd frontend
corepack pnpm install
corepack pnpm dev
```

前端路由加载检查：

- `http://localhost:5173/login`
- `http://localhost:5173/app`
- `http://localhost:5173/admin`

## 连通性检查

- MySQL 连通性：确认 `DATABASE_URL` 指向的 `weview_mvp` 数据库可连接。
- Milvus 连通性：确认 `MILVUS_HOST` 和 `MILVUS_PORT` 指向本地 Milvus Standalone。
- DashScope 连通性：自动化测试不检查真实模型；真实模型调用只在手动冒烟检查中执行。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend
cd frontend
corepack pnpm test:unit
```

后续阶段会增加 Playwright smoke tests，和后端、前端单元测试分开执行。
