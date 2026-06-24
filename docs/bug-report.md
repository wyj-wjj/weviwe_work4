# 🔴 WeView Work4 MVP — 测试 Bug 报告

> **测试日期**：2026-06-22
> **测试人员**：QA (自动化 API 黑盒测试)
> **测试方法**：通过 `curl` 直接调用 FastAPI 后端接口，结合 MySQL 数据库直接查询验证
> **测试环境**：`http://127.0.0.1:8000`（后端）+ `http://127.0.0.1:5173`（前端）
> **数据库**：MySQL 8.4, 库名 `weview_mvp`
> **种子数据**：`data/seed_energy_storage.py` 已执行（23 条内容，3 个测试账号）

---

## 📊 全局测试通过率

| 模块 | 通过 / 总数 | 通过率 |
|------|:-----------:|:------:|
| 基础设施 | 3 / 3 | 100% |
| 登录与权限 | 6 / 7 | 86% |
| 后台内容管理 | 0 / 15 | **0%** |
| 员工端内容查看 | 0 / 9 | **0%** |
| AI 问答 | 0 / 18 | **0%** |
| 巩固测试 | 0 / 6 | **0%** |
| 未命中问题管理 | 4 / 4 | 100% |
| 账号管理 | 8 / 8 | 100% |
| **总计** | **21 / 70** | **30%** |

**结论**：登录、账号管理、未命中问题三个模块正常。所有与 `contents` / `content_versions` 表相关的 API 全部返回 500。只有一个根因 Bug。

---

---

## 🐛 Bug #1 [致命] 数据库迁移未执行 —— 所有内容相关 API 返回 500

### 严重程度

🔴 **致命 (Blocker)** — 阻塞 49/70 个测试用例（70%），包含 AI 问答等核心功能。

### 现象

调用以下任一接口，后端返回 `500 Internal Server Error`：

```
GET  /api/admin/contents
GET  /api/app/must-reads
GET  /api/app/scripts
GET  /api/app/quiz
GET  /api/admin/quiz-questions
POST /api/app/rag/ask
```

前端展示：**"服务暂不可用，请稍后重试"**

### 根本原因

**ORM 模型与数据库表结构不一致。**

`backend/app/models/content.py` 第 42-43 行，`Content` 模型定义了两个新增字段：

```python
# backend/app/models/content.py 第 42-43 行
draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
published_draft_revision: Mapped[int | None] = mapped_column(Integer)
```

对应的 Alembic 迁移脚本 `0004_add_publish_revision_and_version_permission.py` 也已存在：

```
backend/alembic/versions/
├── 0001_initial_schema.py                              ← 已执行 ✓
├── 0002_add_content_draft_fields.py                    ← 已执行 ✓
├── 0003_add_content_index_status.py                    ← 已执行 ✓
├── 0004_add_publish_revision_and_version_permission.py ← 未执行 ✗
```

但 **MySQL 数据库中从未执行过 `0004` 迁移**，`contents` 表缺少这两个列：

| MySQL `contents` 表实际列 | ORM 模型 `Content` 定义的列 | 状态 |
|---|---|---|
| `draft_summary` | `draft_summary` | ✅ 匹配 |
| `draft_body` | `draft_body` | ✅ 匹配 |
| `draft_payload` | `draft_payload` | ✅ 匹配 |
| ❌ 不存在 | `draft_revision` | ❌ 模型有，表没有 |
| ❌ 不存在 | `published_draft_revision` | ❌ 模型有，表没有 |

SQLAlchemy 生成的每个 `SELECT` 都会自动包含模型中定义的所有列，因此任何对 `contents` 表的查询都会触发：

```
pymysql.err.OperationalError: (1054, "Unknown column 'contents.draft_revision' in 'field list'")
```

### 完整错误堆栈

```
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (1054, "Unknown column 'contents.draft_revision' in 'field list'")
[SQL: SELECT contents.id, contents.content_type, contents.title, contents.category,
      contents.permission_level, contents.status, contents.index_status,
      contents.draft_summary, contents.draft_body, contents.draft_payload,
      contents.draft_revision, contents.published_draft_revision,    ← 这两个列不存在
      contents.current_version_id, contents.created_by,
      contents.created_at, contents.updated_at
FROM contents ORDER BY contents.id DESC LIMIT %(param_1)s]
```

### 迁移 0004 具体要做什么

`backend/alembic/versions/0004_add_publish_revision_and_version_permission.py` 的 `upgrade()` 方法：

```python
def upgrade() -> None:
    # 1) 给 contents 表新增两列
    op.add_column("contents", sa.Column("draft_revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("contents", sa.Column("published_draft_revision", sa.Integer(), nullable=True))

    # 2) 给 content_versions 表新增 permission_level 列
    op.add_column("content_versions", sa.Column("permission_level", sa.String(32), nullable=True))
    op.execute("UPDATE content_versions SET permission_level = (SELECT ... FROM contents WHERE ...)")
    # ALTER COLUMN to NOT NULL after backfill

    # 3) 回填已发布数据的 published_draft_revision
    op.execute("UPDATE contents SET published_draft_revision = draft_revision WHERE current_version_id IS NOT NULL")
```

> ⚠️ 注：迁移 0004 还会给 `content_versions` 表加 `permission_level` 列。当前 `content_versions` 表可能也缺少此列，但由于当前代码不主动 SELECT `content_versions.permission_level`，所以单独查询版本表不会报错。一旦迁移执行后会统一修复。

### 影响范围

**受影响 API (6 个，全部 500)**：

| 接口 | 用途 | 对应文件 |
|------|------|----------|
| `GET /api/admin/contents` | 后台内容列表 + 筛选 + 分页 | `backend/app/api/routes/content.py` 第 45 行 |
| `GET /api/app/must-reads` | 员工最新必读列表 | `backend/app/api/routes/content.py` 第 168 行 |
| `GET /api/app/scripts` | 员工标准话术列表 | `backend/app/api/routes/content.py` 第 220 行 |
| `GET /api/app/quiz` | 员工巩固测试抽题 | `backend/app/api/routes/quiz.py` |
| `GET /api/admin/quiz-questions` | 后台测验题管理列表 | `backend/app/api/routes/quiz.py` |
| `POST /api/app/rag/ask` | AI 问答 | `backend/app/api/routes/rag.py` 第 16 行 |

**不受影响 API (12 个，正常)**：

| 接口 | 原因 |
|------|------|
| `GET /health` | 不访问数据库 |
| `POST /api/auth/login` | 只查 `users` 表 |
| `GET /api/auth/me` | 只查 `users` 表 |
| `GET /api/admin/ping` | 不查表 |
| `GET /api/admin/users` | 只查 `users` 表 |
| `POST /api/admin/users` | 只写 `users` 表 |
| `PATCH /api/admin/users/{id}` | 只写 `users` 表 |
| `POST /api/admin/users/{id}/reset-password` | 只写 `users` 表 |
| `POST /api/admin/users/{id}/disable` | 只写 `users` 表 |
| `GET /api/admin/missed-questions` | 只查 `missed_questions` 表 |
| `POST /api/admin/missed-questions/{id}/mark-handled` | 只写 `missed_questions` 表 |
| `GET /api/admin/contents/{id}/versions` | 只查 `content_versions` 表（不走 `Content` 模型） |

### 修复方法

**在 `backend` 目录下执行**：

```bash
cd E:\WeView\work4\backend
..\\.venv\\Scripts\\alembic.exe upgrade head
```

或：

```bash
cd E:\WeView\work4\backend
..\\.venv\\Scripts\\python.exe -m alembic upgrade head
```

执行后验证（查询 MySQL）：

```sql
-- 确认 draft_revision 列存在
SHOW COLUMNS FROM contents LIKE 'draft_revision';
-- 应返回 1 行

-- 确认当前迁移版本
SELECT * FROM alembic_version;
-- 应显示 0004_publish_revision_permission
```

### 证据

**已执行测试的完整输出**：

```
# 测试内容列表 —— 500
$ curl http://127.0.0.1:8000/api/admin/contents -H "Authorization: Bearer <token>"
Internal Server Error

# 测试必读列表 —— 500
$ curl http://127.0.0.1:8000/api/app/must-reads -H "Authorization: Bearer <token>"
Internal Server Error

# 测试 AI 问答 —— 500
$ curl -X POST http://127.0.0.1:8000/api/app/rag/ask \
  -H "Authorization: Bearer <token>" \
  -d '{"question":"消防要求"}'
Internal Server Error

# 同一后端，测试用户列表 —— 正常
$ curl http://127.0.0.1:8000/api/admin/users -H "Authorization: Bearer <token>"
{"items":[...], "total":17, ...}   ← 正常返回

# 同一后端，测试未命中问题 —— 正常
$ curl http://127.0.0.1:8000/api/admin/missed-questions -H "Authorization: Bearer <token>"
{"items":[...], "total":28, ...}   ← 正常返回
```

**MySQL 直接查询验证**：

```python
# 直接通过 SQLAlchemy 查询 contents 表
stmt = select(Content).order_by(Content.id.desc()).limit(5)
db.scalars(stmt).all()
# → pymysql.err.OperationalError: (1054, "Unknown column 'contents.draft_revision' in 'field list'")
```

---

---

## 🐛 Bug #2 [一般] 禁用账号登录时错误提示不准确

### 严重程度

🟡 **一般 (Minor)** — 用户体验瑕疵，不影响核心功能。

### 现象

当已禁用的账号尝试登录时，返回的错误信息是 **"用户名或密码错误"**，而非"账号已被禁用"。

### 根因

`backend/app/api/routes/auth.py` 第 34 行，登录逻辑将三种失败情况合并为一个通用错误：

```python
# backend/app/api/routes/auth.py 第 33-35 行
user = db.scalar(select(User).where(User.username == payload.username))
if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
    raise invalid_credentials_error()
# → 返回 {"error": {"code": "invalid_credentials", "message": "用户名或密码错误。"}}
```

三个条件（用户不存在、账号已禁用、密码错误）被写在同一行 `if` 中，对外暴露相同的错误码和消息，用户无法区分禁用和被锁定/输错密码。

### 预期行为

- 用户不存在 → `"用户名或密码错误"`（安全考虑，不暴露用户是否存在）
- 密码错误 → `"用户名或密码错误"`
- **账号已禁用** → 应返回如 `"账号已被禁用，请联系管理员"` 或至少一个不同的错误码

### 修复方向

将 `is_active` 检查独立出来：

```python
user = db.scalar(select(User).where(User.username == payload.username))
if user is None or not verify_password(payload.password, user.password_hash):
    raise invalid_credentials_error()
if not user.is_active:
    raise AppError(code="account_disabled", message="账号已被禁用，请联系管理员。", status_code=403)
```

### 证据

```bash
# 创建测试用户
$ curl -X POST /api/admin/users -d '{"username":"qa_test_01",...}' → 成功

# 禁用该用户
$ curl -X POST /api/admin/users/17/disable → {"is_active":false}

# 用正确密码登录 —— 返回的却是 "用户名或密码错误"
$ curl -X POST /api/auth/login -d '{"username":"qa_test_01","password":"正确的密码"}'
{"error":{"code":"invalid_credentials","message":"用户名或密码错误。"}}
# ↑ 用户用的是正确密码！真正原因是账号被禁用
```

---

---

## 🐛 Bug #3 [轻微] 缺少独立的启用账号 API 端点

### 严重程度

🟢 **轻微 (Trivial)** — 有替代方案（通过 PATCH），但缺少对称性。

### 现象

存在 `POST /api/admin/users/{id}/disable` 用于禁用账号，但没有对应的 `POST /api/admin/users/{id}/enable` 来启用账号。

```bash
$ curl -X POST /api/admin/users/17/enable
{"error":{"code":"not_found","message":"Resource not found."}}   ← 404
```

### 当前替代方案

可以通过 `PATCH /api/admin/users/{id}` 设置 `is_active: true` 来启用：

```bash
$ curl -X PATCH /api/admin/users/17 -d '{"is_active":true}'
{"id":17,...,"is_active":true}   ← 成功启用
```

### 修复方向

在 `backend/app/api/routes/user.py` 路由中添加一个 `/enable` 端点（与第 69-75 行的 `/disable` 对称），或在 `backend/app/services/user_service.py` 中添加 `enable_user` 函数。

---

---

## 📋 完整测试结果明细

### ✅ 正常工作的功能

| 接口 | 测试次数 | 状态 |
|------|:---:|:---:|
| `GET /health` | 1 | ✅ |
| `POST /api/auth/login` (正确密码) | 4 | ✅ |
| `POST /api/auth/login` (错误密码) | 1 | ✅ |
| `POST /api/auth/login` (空字段) | 1 | ✅ |
| `GET /api/auth/me` | 1 | ✅ |
| `GET /api/admin/ping` (非管理员) | 1 | ✅ (403) |
| `GET /api/admin/users` | 1 | ✅ |
| `POST /api/admin/users` | 1 | ✅ |
| `PATCH /api/admin/users/{id}` | 2 | ✅ |
| `POST /api/admin/users/{id}/reset-password` | 2 | ✅ |
| `POST /api/admin/users/{id}/disable` | 1 | ✅ |
| `GET /api/admin/missed-questions` | 2 | ✅ |
| `POST /api/admin/missed-questions/{id}/mark-handled` | 1 | ✅ |
| 前端 Vite 服务 | 1 | ✅ (HTTP 200) |

### ❌ 异常的接口

| 接口 | HTTP 状态 | 错误 |
|------|:---:|------|
| `GET /api/admin/contents` | 500 | `Unknown column 'contents.draft_revision'` |
| `GET /api/app/must-reads` | 500 | 同上 |
| `GET /api/app/scripts` | 500 | 同上 |
| `GET /api/app/quiz` | 500 | 同上 |
| `GET /api/admin/quiz-questions` | 500 | 同上 |
| `POST /api/app/rag/ask` | 500 | 同上 |

---

## 🔧 修复优先级

| 优先级 | Bug | 修复操作 | 预计影响 |
|:---:|---|---|---|
| 🔴 P0 | #1 迁移未执行 | 执行 `alembic upgrade head` | 恢复 70% 的 API |
| 🟡 P2 | #2 登录错误消息 | 拆分 `is_active` 检查 | 提升 UX |
| 🟢 P3 | #3 缺少 enable 端点 | 添加 `/enable` 路由 | API 对称性 |

**修复 P0 后需要重新执行全量回归测试（70 个用例）。**
