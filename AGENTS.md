# AGENTS.md

## 项目概述

这是企业话术智能检索与统一培训管理系统 MVP。

首期目标是跑通以下业务闭环：

1. 管理员维护并发布官方话术内容。
2. 系统按权限隔离通用级和全量级内容。
3. 员工在前台查看最新必读、标准话术和巩固测试。
4. 员工通过 AI 问答检索当前权限内的有效话术。
5. AI 回答必须基于已发布、未失效、当前用户可见的话术来源。
6. 未命中问题进入后台列表，供管理员后续补充内容。

## 必读上下文

开始任何实现工作前，先阅读：

- `memory-bank/architecture.md`
- `memory-bank/design-document.md`
- `memory-bank/tech-stack.md`

其中 `memory-bank/architecture.md` 是工程架构和实现边界的最新记忆文件；`memory-bank/design-document.md` 是产品设计基线。

## 推荐技术栈

- 前端：Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios、Element Plus。
- 后端：Python 3.13.x、FastAPI、Pydantic v2、SQLAlchemy 2.x、Alembic、PyMySQL。
- 数据库：MySQL 8.4 LTS。
- 向量数据库：Milvus Standalone、PyMilvus。
- 模型服务：DashScope OpenAI-compatible `qwen-plus`，DashScope `text-embedding-v4`。
- 测试：pytest、Vitest、Playwright。

## 架构原则

- 首期采用 FastAPI 单体后端，不拆微服务。
- MySQL 是唯一权威数据源。
- Milvus 只作为向量检索索引，不作为权威正文来源。
- AI 回答前必须从 MySQL 回查正文。
- 权限校验以后端为准，前端隐藏入口不能替代后端权限控制。
- 不在 MVP 首期引入 LangChain、LangGraph、Celery、Redis、Kubernetes 或微服务。

## 权限规则

系统账号类型：

- `admin`：管理员，可进入后台，可查看通用级和全量级内容。
- `full_user`：完整权限员工，不可进入后台，可查看通用级和全量级内容。
- `general_user`：通用权限员工，不可进入后台，仅可查看通用级内容。

内容权限：

- `general`：通用级。
- `full`：全量级。

所有列表、详情、AI 检索、历史版本、测验题接口都必须按当前账号权限过滤。

## 开发规则

- 改动前先检查 `git status --short`，避免覆盖用户未提交改动。
- 手动编辑文件时优先使用 `apply_patch`。
- 不要提交 `.env`、密钥、数据库密码、DashScope API Key 或其他敏感信息。
- 新增依赖前先确认是否确实服务于 MVP。
- 新增功能应配套测试；无法测试时在最终说明中写清原因。
- 完成重大功能或里程碑后，更新 `memory-bank/architecture.md`。

## Git 规则

- 默认分支：`main`。
- 远端仓库：`https://github.com/wyj-wjj/weviwe_work4.git`。
- 提交前检查工作区，只提交本次任务相关文件。
- 不要回滚或覆盖用户未明确要求处理的改动。

## 重要提示

写任何代码前必须完整阅读memory-bank/architecture.md

写任何代码前必须完整阅读memory-bank/design-document.md

每完成一个重大功能或里程碑后，必须更新memory-bank/architecture.md
