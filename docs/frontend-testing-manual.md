# 阶段 8 前端手测操作手册

本手册用于从浏览器验证员工端功能：登录、员工首页、最新必读、标准话术、巩固测试和 AI 问答结果页。阶段 8 还没有后台管理前端页面，所以测试数据需要先通过脚本或已有后台 API 准备。

## 1. 准备环境

确认本机已具备：

- MySQL 8.x，建议库名 `weview_mvp`。
- Python 虚拟环境 `.venv` 已安装后端依赖。
- Node/Corepack/pnpm 可用。
- Milvus 只在测试真实 AI 命中时需要；只测页面、登录、内容列表、测验时可以先不启动。

不要把 `.env`、数据库密码、DashScope API Key 或 JWT 密钥提交到仓库。

## 2. 配置后端 `.env`

在项目根目录 `E:\WeView\work4\.env` 准备本地配置。示例：

```powershell
DATABASE_URL=mysql+pymysql://<mysql-user>:<mysql-password>@localhost:3306/weview_mvp
JWT_SECRET_KEY=<至少32位的本地随机字符串>
USE_FAKE_EXTERNAL_CLIENTS=true
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=weview_content_chunks
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=qwen-plus
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
RAG_SIMILARITY_THRESHOLD=0.7
RAG_TOP_K=5
```

说明：

- `USE_FAKE_EXTERNAL_CLIENTS=true` 适合先测前端页面和基础接口，不需要 DashScope API Key。
- 要测试真实 AI 命中，把 `USE_FAKE_EXTERNAL_CLIENTS=false`，补充 `DASHSCOPE_API_KEY`，并启动 Milvus。
- `DASHSCOPE_API_KEY` 不需要用于登录、最新必读、标准话术和巩固测试；只用于真实 embedding 与 AI 回答。

## 3. 初始化数据库

先创建库并执行迁移：

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

如果库还不存在，先用 MySQL 客户端创建：

```sql
CREATE DATABASE IF NOT EXISTS weview_mvp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
```

## 4. 写入手测数据

阶段 8 提供了本地 seed 脚本：`docs/seed-phase8-manual-data.py`。它会创建或更新三个本地账号，并写入最新必读、基础话术、标准话术、全量权限话术和 5 道测验题。

在项目根目录运行：

```powershell
cd E:\WeView\work4
$env:PYTHONPATH='backend'
$env:DATABASE_URL='mysql+pymysql://<mysql-user>:<mysql-password>@localhost:3306/weview_mvp'
$env:WEVIEW_MANUAL_PASSWORD='<你自定义的手测密码>'
.\.venv\Scripts\python.exe docs\seed-phase8-manual-data.py
```

脚本创建的账号：

- `phase8_manual_general`：通用权限员工，只能看通用级内容。
- `phase8_manual_full`：完整权限员工，可以看通用级和全量级内容。
- `phase8_manual_admin`：管理员账号，阶段 8 前端暂未实现后台页面，但可用于后续后台阶段。

脚本会把这三个账号的密码更新为你设置的 `WEVIEW_MANUAL_PASSWORD`。

## 5. 启动后端

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

验证：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
```

预期返回包含 `"status":"ok"`。

## 6. 启动前端

前端默认使用同源 `/api`，Vite 会把 `/api` 代理到后端。首次启动前可在 `frontend/.env.local` 写入：

```powershell
VITE_API_BASE_URL=/api
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

启动：

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm install
corepack.cmd pnpm exec vite --host 127.0.0.1 --port 5173
```

浏览器打开：

```text
http://127.0.0.1:5173/login
```

## 7. 登录测试

用通用员工登录：

- 用户名：`phase8_manual_general`
- 密码：你在 `WEVIEW_MANUAL_PASSWORD` 设置的值

登录成功后应进入 `/app`。页面应显示：

- 顶部员工身份与退出登录按钮。
- AI 问答输入框和“提问”按钮。
- 三个入口：最新必读、标准话术、巩固测试。

再用 `phase8_manual_full` 登录，使用相同的自定义手测密码，可对比全量权限内容是否多出来。

## 8. 员工首页操作

在 `/app`：

1. 直接点“提问”，应提示请输入问题。
2. 输入任意问题，例如“风险提示怎么说”，点“提问”。
3. 页面跳转到 `/app/ask?question=...`。
4. 如果没有真实索引，AI 页显示“当前没有有效标准口径，请联系管理员。”属于正常未命中状态。

## 9. 最新必读

入口：`/app/must-reads`

检查点：

- 列表显示标题、发布时间、生效时间和权限级别。
- 点击“阶段8手测：新版产品介绍口径”进入详情。
- 详情页显示更新正文、调整要点和权限级别。
- `phase8_manual_general` 不应看到全量级内容。

如果列表为空，优先确认：

- 是否运行了 seed 脚本。
- 内容是否为 `published`。
- 当前登录账号权限是否匹配。
- 后端是否连接到同一个 MySQL 库。

## 10. 标准话术

入口：`/app/scripts`

检查点：

- 页面分为“核心基础话术”和“标准化话术”。
- 场景分类下拉可按“开场”“风控”“全量场景”等分类过滤。
- 点击“阶段8手测：基础开场白”，详情应显示正文、要点和复制按钮。
- 点击“阶段8手测：风险提示标准话术”，详情应显示适用场景、推荐说法、禁用说法、备注和复制按钮。
- 用 `phase8_manual_full` 登录后，应可看到“阶段8手测：全量权限专属话术”；通用员工不应看到。

复制按钮会调用浏览器剪贴板。如果浏览器限制剪贴板权限，按钮会显示失败提示，但不影响内容读取。

## 11. 巩固测试

入口：`/app/quiz`

检查点：

- 页面显示 5 到 10 道当前权限可见的启用题目。
- 每道题独立选择答案。
- 点击“提交答案”后，按钮短暂进入提交中状态。
- 返回结果显示“回答正确”或“回答错误”、正确答案、解析和关联话术入口。
- 页面不显示分数历史、排行或个人统计，这是 MVP 明确不做的范围。

## 12. AI 问答

入口：员工首页提问，或直接访问 `/app/ask?question=风险提示`

三种常见结果：

- 命中：显示回答、来源列表、来源更新时间、复制回答按钮和“查看来源”链接。
- 未命中：显示“当前没有有效标准口径，请联系管理员。”。
- AI 不可用：显示智能问答暂不可用提示，通常由 DashScope/Milvus 配置或服务异常导致。

只用 `USE_FAKE_EXTERNAL_CLIENTS=true` 时，适合验证前端状态和未命中展示；真实 AI 命中需要：

1. Milvus Standalone 正常运行。
2. `USE_FAKE_EXTERNAL_CLIENTS=false`。
3. `.env` 中补充有效 `DASHSCOPE_API_KEY`。
4. 内容发布后通过后端索引流程写入 Milvus。

阶段 8 没有后台前端索引按钮；可以用后端后台 API 或后续阶段 9 页面触发 `POST /api/admin/contents/{content_id}/retry-index`。

## 13. 常见问题

登录后立刻回到登录页：

- token 过期或后端重启后 `JWT_SECRET_KEY` 变化，重新登录即可。
- 确认前端请求走的是 `/api/auth/login`，不要打到 `/auth/login`。

前端接口 404：

- 确认 `VITE_API_BASE_URL=/api`。
- 确认 Vite 代理目标是当前后端：`VITE_API_PROXY_TARGET=http://127.0.0.1:8000`。
- 确认当前 8000 进程是本项目后端，`/openapi.json` 应包含 `/api/auth/login`。

页面提示服务暂不可用：

- 后端未启动、数据库不可连，或 Vite 代理目标错误。
- 后端日志优先看启动命令窗口。

列表为空：

- 重新运行 seed 脚本。
- 确认登录账号类型；通用员工不会看到全量级内容。

AI 一直未命中：

- 只测前端时这是可接受结果。
- 要测真实命中，需要 DashScope API Key、Milvus 和已完成索引的内容。

## 14. 推荐验证命令

前端单测：

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm test:unit
```

前端构建：

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm build
```

后端测试：

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest
```
