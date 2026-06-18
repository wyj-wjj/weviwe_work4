# 前端真实全链路操作测试手册

本手册用于从浏览器验证完整 MVP：管理员后台、员工端、MySQL、Milvus 和真实 DashScope AI。执行日期基线为 2026-06-18。

## 1. 测试原则

- 必须使用真实 MySQL。
- 必须使用真实 Milvus Standalone。
- 必须设置 `USE_FAKE_EXTERNAL_CLIENTS=false` 并使用真实 DashScope。
- 除首个管理员外，所有测试数据都从管理员前端操作，经 FastAPI API 写入。
- 内容必须在管理员前端点击“发布”，由正式发布流程写入 MySQL 版本/chunk，并调用 embedding 写入 Milvus。
- 不得使用阶段 10 SQLite 夹具。
- 不得运行 `docs/seed-phase8-manual-data.py` 准备本次验收数据；该脚本会直写数据库，不符合本手册的真实 API 流程要求。
- 不在截图、日志、命令历史或仓库中保存真实密码和 `DASHSCOPE_API_KEY`。

## 2. 测试目标

完成后应验证：

1. 管理员可以维护账号、内容、测验题和未命中问题。
2. 通用员工只能看到通用级内容。
3. 完整权限员工能看到通用级和全量级内容。
4. 发布内容会生成版本、chunk、索引记录和 Milvus 向量。
5. AI 回答基于当前用户可见的已发布内容并展示来源。
6. AI 未命中返回固定文案并进入后台。
7. 测验只返回即时解析，不保存分数或答题历史。

## 3. 准备本地配置

根目录 `.env` 使用真实本地值：

```dotenv
DATABASE_URL=mysql+pymysql://<mysql-user>:<url-encoded-password>@127.0.0.1:3306/weview_mvp
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=weview_content_chunks_real_v4
DASHSCOPE_API_KEY=<your-local-key>
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=qwen-plus
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
RAG_SIMILARITY_THRESHOLD=0.7
RAG_TOP_K=5
JWT_SECRET_KEY=<至少32位随机字符串>
USE_FAKE_EXTERNAL_CLIENTS=false
```

前端 `frontend/.env.local`：

```dotenv
VITE_API_BASE_URL=/api
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

如果本机已有旧 Milvus collection，且曾使用 3 维假向量或其他 embedding 模型，请使用新的 collection 名称，例如 `weview_content_chunks_real_v4`。

## 4. 启动 MySQL 和 Milvus

确认 MySQL 数据库存在：

```sql
CREATE DATABASE IF NOT EXISTS weview_mvp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
```

使用官方 Milvus Standalone Docker Compose 启动 Milvus，然后检查：

```powershell
Test-NetConnection 127.0.0.1 -Port 3306
Test-NetConnection 127.0.0.1 -Port 19530
```

两项都应显示 `TcpTestSucceeded : True`。

## 5. 安装、迁移和创建初始管理员

```powershell
cd E:\WeView\work4
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"

cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
cd ..
```

创建或更新初始管理员：

```powershell
$env:PYTHONPATH='backend'
$env:INITIAL_ADMIN_USERNAME='manual_admin'
$env:INITIAL_ADMIN_DISPLAY_NAME='真实链路管理员'
$env:INITIAL_ADMIN_PASSWORD='<本次手测密码>'
.\.venv\Scripts\python.exe -m app.cli.create_admin
Remove-Item Env:INITIAL_ADMIN_PASSWORD
```

初始管理员是启动引导的唯一直接数据库写入。后续员工账号、内容和测验必须从管理员前端创建。

## 6. 启动后端、前端和 AI

后端窗口：

```powershell
cd E:\WeView\work4
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

前端窗口：

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm install
corepack.cmd pnpm dev
```

浏览器打开 `http://127.0.0.1:5173/login`。此时 AI 已随 FastAPI 启动：发布调用真实 DashScope embedding，问答调用真实 Milvus 检索和 `qwen-plus`。

## 7. 管理员登录与后台导航

使用 `manual_admin` 登录，预期进入 `/admin`，并看到：

- 内容管理。
- 测验题管理。
- 账号管理。
- 未命中问题。
- 当前管理员展示名和退出登录。

打开浏览器开发者工具 Network，后续操作应请求 `/api/...`，不应出现浏览器直接访问 DashScope 域名。

## 8. 从管理员前端创建员工账号

进入“账号管理”，创建：

| 用户名 | 展示名 | 账号类型 | 内容权限 |
| --- | --- | --- | --- |
| `manual_general` | 真实链路通用员工 | 通用权限员工 | 通用级 |
| `manual_full` | 真实链路完整员工 | 完整权限员工 | 全量级 |

密码由测试人员现场填写，不记录在文档。

检查：

- 两个账号显示启用。
- 重复用户名被拒绝。
- 管理员账号为只读。
- Network 中创建请求为 `POST /api/admin/users`。

## 9. 从管理员前端创建并发布内容

进入“内容管理”，使用“新建内容”依次创建以下六条测试数据。每条先保存草稿，再回到列表点击“发布”并确认。

### 9.1 通用最新必读

- 标题：`真实链路：通用最新必读`
- 类型：最新必读
- 分类：真实链路更新
- 权限：通用级
- 摘要：通用员工必读
- 正文/更新正文：`本周客户沟通必须先确认需求，再使用已发布标准口径。`
- 调整要点：每行一项，例如“确认需求”“引用正式口径”

### 9.2 全量最新必读

- 标题：`真实链路：全量最新必读`
- 类型：最新必读
- 分类：真实链路更新
- 权限：全量级
- 正文：`仅完整权限员工可见的内部沟通更新。`

### 9.3 通用基础话术

- 标题：`真实链路：通用开场话术`
- 类型：核心基础话术
- 分类：真实链路开场
- 权限：通用级
- 摘要：`先问候客户`、`确认客户需求`
- 正文：`您好，请先介绍您的核心需求，我们会依据公司已发布的正式口径为您说明。`

### 9.4 全量基础话术

- 标题：`真实链路：全量内部话术`
- 类型：核心基础话术
- 分类：真实链路全量
- 权限：全量级
- 正文：`这是仅完整权限员工可以使用的内部完整口径。`

### 9.5 通用标准化话术

- 标题：`真实链路：风险提示标准话术`
- 类型：标准化话术
- 分类：真实链路风控
- 权限：通用级
- 场景：客户询问风险
- 推荐说法：`相关信息请以公司当前已发布、仍有效的正式口径为准。`
- 禁用说法：`不要承诺未发布的信息。`
- 注意事项：`不使用模型常识补充业务结论。`

### 9.6 全量标准化话术

- 标题：`真实链路：完整权限标准话术`
- 类型：标准化话术
- 分类：真实链路全量
- 权限：全量级
- 场景：完整权限内部沟通
- 推荐说法：`这是完整权限范围内的标准表达。`
- 禁用说法：`不得向通用权限员工透露。`

每次发布后检查：

- 状态为“已发布”。
- 版本为 `v1`。
- 索引状态为“已同步”。
- 若显示“同步失败”，先看后端日志，确认 DashScope Key、Milvus 端口和 collection 维度，再点击“重试索引”。
- Network 中先有内容创建 API，再有 `POST /api/admin/contents/{id}/publish`。

## 10. 历史版本和下线测试

选择“真实链路：通用开场话术”：

1. 点击“编辑”，修改正文并保存草稿。
2. 再次发布。
3. 检查版本变为 `v2`。
4. 点击“历史”，应看到 v1、v2 的标题、发布时间、发布人和正文快照。
5. 员工端只应看到 v2。

选择一条非核心测试内容执行“下线”：

- 员工列表中应消失。
- AI 来源中不应再出现。
- 下线内容不能继续发布。

## 11. 从管理员前端创建测验题

进入“测验题管理”，至少创建：

- 5 道通用级启用题，关联通用话术。
- 1 道全量级启用题，关联全量话术。

每道题填写题干、至少两个选项、正确答案和解析。检查启用/禁用动作会刷新状态。

## 12. 通用员工权限测试

退出管理员，使用 `manual_general` 登录。

### 最新必读

- 能看到“真实链路：通用最新必读”。
- 看不到“真实链路：全量最新必读”。

### 标准话术

- 能看到通用基础话术和通用标准化话术。
- 看不到任何全量标题、正文、分类或来源。
- 复制按钮能复制当前详情文本。

### 直接详情越权

从管理员记录一条全量内容 ID，直接访问相应员工详情 URL。

预期显示“无权查看该内容”，页面不残留标题、正文、来源和更新时间。

### 巩固测试

- 只出现通用级启用题。
- 提交后显示对错、正确答案和解析。
- 刷新页面后不显示答题历史、分数、排行或统计。

## 13. 完整权限员工测试

退出并使用 `manual_full` 登录。

- 最新必读同时显示通用级和全量级。
- 标准话术同时显示通用级和全量级。
- 巩固测试可出现通用题和全量题。
- 仍然不能进入 `/admin`，访问时应回到员工端。

## 14. 真实 AI 问答命中测试

使用通用员工在首页提问：

```text
客户询问风险时，标准提示应该怎么说？
```

预期：

- 页面显示由 `qwen-plus` 生成的回答。
- 来源至少包含“真实链路：风险提示标准话术”或其他当前账号可见的通用内容。
- 每个来源显示内容类型、更新时间和“查看来源”。
- 来源详情能打开。
- 来源中绝不出现全量级标题。

使用完整权限员工提问：

```text
完整权限内部沟通可以使用什么标准表达？
```

预期允许返回全量级来源。

这条流程实际经过：

```text
Vue -> POST /api/app/rag/ask
  -> DashScope text-embedding-v4
  -> Milvus 权限过滤召回
  -> MySQL 回查当前版本正文
  -> DashScope qwen-plus
  -> 回答和来源返回前端
```

## 15. 真实 AI 未命中测试

使用通用员工提出与话术库明显无关的问题，例如：

```text
请给出火星基地明天的食堂菜单和负责人电话。
```

预期：

- 显示“当前没有有效标准口径，请联系管理员。”。
- 不让模型自由补充答案。
- 管理员重新登录后，在“未命中问题”列表看到该问题、账号、权限快照和时间。
- 点击“标记已处理”后状态和处理时间更新。

如果无关问题仍命中，说明当前阈值或内容过宽。可提高 `RAG_SIMILARITY_THRESHOLD` 后重启后端再测。

## 16. 账号禁用和密码重置

管理员前端：

1. 重置 `manual_general` 密码。
2. 用旧密码登录应失败，新密码应成功。
3. 禁用 `manual_general`。
4. 禁用后新登录应失败。
5. 已有 token 再请求受保护 API 也应返回认证错误并跳回登录页。

## 17. MySQL 与 Milvus 只读核验

前端操作完成后，可以只读确认数据确实落在真实服务。

MySQL：

```sql
SELECT username, account_type, content_level, is_active
FROM users
WHERE username IN ('manual_admin', 'manual_general', 'manual_full');

SELECT id, title, status, current_version_id, index_status
FROM contents
WHERE title LIKE '真实链路：%';

SELECT content_id, version_no, title, published_at
FROM content_versions
WHERE title LIKE '真实链路：%';

SELECT content_id, version_id, chunk_id, milvus_collection, embedding_model, embedding_dimension, is_active
FROM vector_index_records
WHERE milvus_collection = 'weview_content_chunks_real_v4';
```

Milvus 使用 PyMilvus 只读检查 collection 是否存在、实体数量是否增加。不要从 Milvus读取正文作为权威数据；正文必须以 MySQL `content_versions` 为准。

## 18. 完成判定

真实链路通过时，在 `docs/mvp-acceptance-checklist.md` 第 14 条记录：

- 执行日期。
- MySQL 数据库名。
- Milvus collection 名。
- DashScope chat/embedding 模型名。
- 发布后索引状态。
- 通用/完整权限隔离结果。
- AI 命中与未命中结果。

不要记录数据库密码、账号密码、API Key、JWT 密钥或完整 token。

## 19. 自动化回归

真实手测完成后仍需运行：

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest

cd E:\WeView\work4\frontend
corepack.cmd pnpm test:unit
corepack.cmd pnpm build
corepack.cmd pnpm test:e2e
```

自动化 E2E 使用阶段 10 SQLite/假客户端环境，只证明行为可重复；它不能替代本手册的真实 MySQL、Milvus 和 DashScope 验收。

## 20. 常见问题

### Alembic 仍连接占位账号

- 确认根目录 `.env` 存在且 `DATABASE_URL` 正确。
- 从 `backend` 目录执行 `..\.venv\Scripts\python.exe -m alembic upgrade head`。

### 发布后索引失败

- 确认 `USE_FAKE_EXTERNAL_CLIENTS=false`。
- 确认 DashScope API Key 与北京地域 endpoint 匹配。
- 确认 19530 可访问。
- 使用新的 Milvus collection，避免旧 collection 向量维度不一致。

### AI 服务不可用

- 后端 503 且 `provider_authentication_failed`：Key 无效或地域不匹配。
- `provider_timeout`：网络或 DashScope 超时。
- `provider_response_invalid`：供应商返回格式异常。
- Milvus 连接失败时，内容列表和测验仍应可用。

### 前端接口 404

- 确认 `VITE_API_BASE_URL=/api`。
- 确认 `VITE_API_PROXY_TARGET=http://127.0.0.1:8000`。
- 确认 8000 端口运行的是本项目 FastAPI。
