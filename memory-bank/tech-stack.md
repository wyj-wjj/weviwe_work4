# 企业话术智能检索与统一培训管理系统 MVP 技术栈推荐

## 1. 结论摘要

基于 `memory-bank/design-document.md` 的产品范围，首期推荐采用“前后端分离 + 单体后端服务 + MySQL 权威数据源 + Milvus 向量索引 + DashScope 模型服务”的技术栈。

推荐主栈：

| 层级 | 推荐技术 | 选择理由 |
| --- | --- | --- |
| 前端 | Vue 3 + TypeScript + Vite | 与需求文档一致，适合中后台和移动 H5，开发轻量 |
| 前端路由 | Vue Router | Vue 官方生态，满足前台与后台路由隔离 |
| 前端状态 | Pinia | Vue 官方推荐方向，API 简单，适合登录态和用户权限 |
| 前端请求 | Axios | 简单稳定，便于统一处理 token、错误码和权限异常 |
| 前端 UI | Element Plus + 少量自定义移动端样式 | 管理后台表格/表单效率高，员工端页面较简单，可用自定义响应式样式补足 |
| 后端 | Python 3.13.x + FastAPI | 类型友好、OpenAPI 自动生成、适合 API 与 RAG 服务编排 |
| 数据校验 | Pydantic v2 | FastAPI 核心生态，适合请求/响应模型和配置校验 |
| ORM | SQLAlchemy 2.x | 成熟稳健，适合 MySQL 数据模型和事务控制 |
| 迁移 | Alembic | SQLAlchemy 官方生态迁移工具 |
| 业务数据库 | MySQL 8.4 LTS | 当前更适合新项目的 MySQL LTS 线，承载权威业务数据 |
| 向量数据库 | Milvus Standalone + PyMilvus | 与 PRD 一致，首期用 Docker 本地运行，后续可迁移 |
| 生成模型 | 阿里云 DashScope OpenAI-compatible + `qwen-plus` | 与 PRD 一致，后端统一封装，前端不直接调用 |
| Embedding | 阿里云 `text-embedding-v4` | 与 PRD 一致，适合中文话术语义检索 |
| 测试 | pytest + Vitest + Playwright | 分别覆盖后端单元/API、前端组件、关键端到端流程 |
| 部署 | 本地开发直跑 + Docker 运行依赖；上线用 Nginx + ECS | 首期简单可控，后续上云路径清晰 |

核心建议：不要在 MVP 首期引入 LangChain、LangGraph、Celery、Redis、Kubernetes、微服务或复杂 BFF。当前系统的复杂点不是服务数量，而是权限、版本、索引同步和 RAG 回答边界，这些更适合在一个清晰的 FastAPI 单体服务里先做扎实。

## 2. 技术选型目标

首期技术栈应满足以下目标：

- 简单：团队可以快速理解目录、启动方式和调试方式。
- 健壮：权限、版本、索引状态、AI 未命中、外部服务失败都有明确处理。
- 可迁移：本地验证通过后能平滑部署到阿里云 ECS。
- 可测试：权限隔离、内容发布、RAG 命中、未命中记录必须能自动化验证。
- 可扩展：二期增加文档解析、多岗位权限、混合检索时不推倒重来。

## 3. 总体架构

```text
浏览器 / 微信内置浏览器
  -> Vue 3 SPA
    -> REST API
      -> FastAPI 单体后端
        -> MySQL 8.4 LTS：账号、权限、内容、版本、chunk、测验、未命中问题
        -> Milvus Standalone：向量索引和过滤元数据
        -> DashScope：chat completion 和 text embedding
```

### 3.1 架构形态

首期采用单体后端，不拆微服务。

推荐原因：

- 权限校验、内容版本、RAG 检索、MySQL 回查和来源返回强相关，放在一个服务里更容易保证一致性。
- MVP 流量和团队规模通常不需要微服务。
- 单体服务更容易本地启动、调试、测试和部署。
- 后续如果 AI 索引同步压力上来，再拆独立 worker 或任务队列。

### 3.2 API 风格

推荐使用 REST API，不引入 GraphQL。

原因：

- 页面结构和数据对象明确，REST 足够表达。
- FastAPI 自动生成 OpenAPI 文档，便于前后端联调。
- 权限边界更容易按接口和资源控制。

## 4. 前端技术栈

### 4.1 推荐组合

| 类型 | 技术 | 用途 |
| --- | --- | --- |
| 构建工具 | Vite | 本地开发和生产构建 |
| 框架 | Vue 3 | 员工端和后台管理端 |
| 语言 | TypeScript | 提高接口、权限状态、表单模型的可靠性 |
| 路由 | Vue Router | 前台、后台、登录态路由控制 |
| 状态管理 | Pinia | 用户信息、权限、token、全局 UI 状态 |
| HTTP 请求 | Axios | API 封装、拦截器、错误处理 |
| UI 组件 | Element Plus | 后台表格、表单、弹窗、分页 |
| 前端测试 | Vitest + Vue Test Utils | 组件和工具函数测试 |
| E2E 测试 | Playwright | 登录、权限隔离、内容发布等关键流程 |
| 代码质量 | ESLint + Prettier | 保持代码风格一致 |

### 4.2 前端目录建议

```text
frontend/
  src/
    api/
    assets/
    components/
    layouts/
    pages/
      auth/
      app/
      admin/
    router/
    stores/
    styles/
    types/
    utils/
```

### 4.3 页面实现策略

- 同一个 Vue 工程承载员工端和后台端。
- 路由按 `/app/*` 和 `/admin/*` 分区。
- 登录页共用。
- 员工端优先移动 H5 体验。
- 后台端优先 PC 表格和表单效率。
- 权限入口前端可隐藏，但安全控制必须以后端为准。

### 4.4 UI 组件策略

推荐使用 Element Plus 作为基础组件库，主要服务后台管理端。

员工端页面较少，建议使用自定义响应式布局和少量 Element Plus 基础组件，不再单独引入移动端 UI 库。这样可以避免 Vant、Element Plus 双组件体系带来的样式割裂和维护成本。

### 4.5 前端暂不引入

- Nuxt：当前没有 SSR、SEO 或服务端渲染需求。
- 微前端：前后台页面可以由一个 SPA 清晰承载。
- 大型状态机库：当前业务状态不需要。
- 多套 UI 组件库：会增加样式和交互一致性成本。

## 5. 后端技术栈

### 5.1 推荐组合

| 类型 | 技术 | 用途 |
| --- | --- | --- |
| 语言 | Python 3.13.x | 生态稳定，兼容性优于追最新大版本 |
| Web 框架 | FastAPI | REST API、鉴权、OpenAPI 文档 |
| ASGI 服务 | Uvicorn | 本地和生产运行 FastAPI |
| 数据校验 | Pydantic v2 | 请求、响应、配置模型 |
| ORM | SQLAlchemy 2.x | MySQL 数据访问和事务 |
| 数据库迁移 | Alembic | 版本化管理表结构 |
| MySQL 驱动 | PyMySQL | 同步 SQLAlchemy 连接，简单稳定 |
| HTTP 客户端 | httpx | 调用 DashScope embedding 或其他 HTTP API |
| OpenAI-compatible SDK | openai | 调用 DashScope chat completion，统一模型接口 |
| 向量 SDK | PyMilvus | 连接 Milvus、写入和检索向量 |
| 密码哈希 | pwdlib[argon2] 或 argon2-cffi | 安全存储账号密码 |
| JWT | python-jose[cryptography] 或 PyJWT | 访问令牌签发与校验 |
| 测试 | pytest + FastAPI TestClient | 后端单元和 API 测试 |

### 5.2 同步还是异步

首期推荐后端以同步 SQLAlchemy 为主，FastAPI 仍作为 API 框架使用。

理由：

- MySQL CRUD 和后台管理场景以事务一致性为主，吞吐不是首要瓶颈。
- 同步 SQLAlchemy + PyMySQL 更容易调试和测试。
- AI 调用和 Milvus 检索可以封装在服务层，后续需要时再局部异步化。
- 避免一开始引入 async SQLAlchemy、async MySQL driver、任务队列等额外复杂度。

如果后续 AI 问答并发明显增加，再评估：

- 将 DashScope 和 Milvus 调用改为异步。
- 增加独立 worker 处理索引同步。
- 引入 Redis 或消息队列做限流和任务调度。

### 5.3 后端目录建议

```text
backend/
  app/
    api/
      routes/
      deps.py
    core/
      config.py
      security.py
      errors.py
    db/
      base.py
      session.py
      migrations/
    models/
    schemas/
    services/
      auth_service.py
      content_service.py
      quiz_service.py
      rag_index_service.py
      rag_search_service.py
      rag_answer_service.py
      missed_question_service.py
    repositories/
    integrations/
      dashscope_client.py
      milvus_client.py
    tests/
  pyproject.toml
```

### 5.4 后端设计要点

- MySQL 是唯一权威数据源。
- Milvus 只保存向量索引和过滤元数据。
- AI 回答前必须从 MySQL 回查正文。
- 权限校验集中在依赖函数和 service 层，不能只靠前端。
- 内容发布、版本生成、旧版本归档、索引状态更新应在一个清晰的 service 流程中完成。
- 生成模型和 embedding 调用必须被封装，业务代码不直接拼外部 API。

## 6. 数据库与存储

### 6.1 MySQL

推荐使用 MySQL 8.4 LTS。

理由：

- 适合账号、权限、内容版本、测验题、未命中问题等结构化数据。
- 与后续阿里云 RDS 迁移路径一致。
- MySQL 8.0 已进入 EOL 阶段，新项目更适合直接使用 8.4 LTS。

### 6.2 Milvus

推荐使用 Milvus Standalone。

使用方式：

- 本地通过 Docker 运行 Milvus。
- 后端通过 PyMilvus 连接。
- 每条向量保留 `content_id`、`version_id`、`chunk_id`、`permission_level`、`status`、`effective_at`、`expired_at` 等过滤元数据。

首期不建议使用托管向量数据库，除非本地 Milvus 维护成本明显高于预期。

### 6.3 文件存储

MVP 首期不做文档上传解析，因此暂不需要对象存储。

二期如果增加 Word/PDF/PPT 上传，再引入阿里云 OSS。

## 7. AI 与 RAG 技术栈

### 7.1 推荐模型接入

| 用途 | 推荐 |
| --- | --- |
| 生成回答 | DashScope OpenAI-compatible + `qwen-plus` |
| 文本向量 | DashScope `text-embedding-v4` |
| 客户端封装 | 后端 `DashScopeClient` |
| 前端调用 | 禁止直接调用模型 API |

### 7.2 SDK 策略

推荐优先使用 OpenAI-compatible SDK 调用生成模型。

Embedding 可采用两种实现方式：

1. 如果 DashScope OpenAI-compatible embedding 接口满足参数需求，优先用同一个 SDK。
2. 如果需要 DashScope 原生 embedding 参数或返回结构，则用 `httpx` 在 `DashScopeEmbeddingClient` 内单独封装。

无论采用哪种方式，业务 service 不直接依赖外部 SDK 的返回结构，应统一转成内部对象。

### 7.3 RAG 编排方式

首期推荐自研确定性 RAG 流程，不引入 LangChain 或 LangGraph。

流程：

```text
鉴权
  -> 生成 query embedding
  -> Milvus 按权限和状态过滤检索
  -> 相似度阈值判断
  -> MySQL 回查正文
  -> 组装上下文
  -> 调用生成模型
  -> 返回回答和来源
  -> 未命中则记录问题
```

理由：

- 当前问答流程固定，不需要 Agent、状态机或复杂工作流。
- 自研服务层更容易把权限、版本和来源一致性做严。
- 后续需要多步工作流、人工审核或长时任务时，再评估 LangGraph。

### 7.4 索引同步策略

首期不引入 Celery 或 Redis。

推荐发布时同步执行以下流程：

1. MySQL 提交内容版本。
2. 生成 chunk。
3. 调用 embedding。
4. 写入 Milvus。
5. 更新 `vector_index_records` 和索引状态。

如果 embedding 或 Milvus 写入失败：

- 内容仍保持已发布。
- 前台仍可查看该内容。
- 索引状态标记为“同步失败”。
- 后台提供“重试索引同步”按钮。

这个策略简单、可追踪，符合 MVP 对“内容可见”和“AI 检索可用性”分离的要求。

## 8. 认证与安全

### 8.1 登录与 token

推荐首期使用账号密码 + JWT access token。

规则：

- 密码使用 Argon2 哈希存储。
- JWT 使用服务端密钥签名。
- token 包含用户 ID、账号类型、内容权限级别和过期时间。
- 前端将 token 放在内存状态和 `sessionStorage`，关闭浏览器后需要重新登录。
- 后端每次请求都从数据库确认用户仍启用，避免禁用账号继续访问。

### 8.2 权限校验

权限校验分两层：

- 路由层：确认登录态和是否管理员。
- service 层：确认内容级别、状态、版本有效性。

所有内容查询必须显式带上权限过滤，不允许先查出全量内容再在前端过滤。

### 8.3 配置与密钥

所有敏感配置必须来自环境变量：

- `DATABASE_URL`
- `MILVUS_HOST`
- `MILVUS_PORT`
- `DASHSCOPE_API_KEY`
- `DASHSCOPE_BASE_URL`
- `DASHSCOPE_CHAT_MODEL`
- `DASHSCOPE_EMBEDDING_MODEL`
- `JWT_SECRET_KEY`

禁止把 API Key、数据库密码或 JWT 密钥写入代码、前端包、示例数据或文档正文。

## 9. 本地开发与部署

### 9.1 本地开发

推荐本地开发形态：

```text
frontend: pnpm dev
backend: uvicorn app.main:app --reload
mysql: 本地 MySQL 或 Docker
milvus: Docker Standalone
```

可以提供 `compose.dev.yml` 管理 MySQL 和 Milvus 等依赖服务，但不要求首期完成生产级 Docker Compose 编排。

### 9.2 包管理

推荐：

- 前端使用 pnpm，并提交 `pnpm-lock.yaml`。
- 后端使用 `pyproject.toml` 管理依赖。
- 如果团队熟悉 `uv`，可使用 `uv.lock` 固定后端依赖版本。
- 如果团队更熟悉传统方式，可用 `requirements.txt`，但需要固定主要依赖版本范围。

### 9.3 上云部署

首期验证通过后，上云推荐：

```text
Nginx
  -> 前端静态资源
  -> /api 反向代理到 FastAPI

FastAPI
  -> MySQL / RDS
  -> Milvus
  -> DashScope
```

部署建议：

- ECS 上运行 FastAPI 和 Nginx。
- MySQL 初期可在 ECS，正式使用建议迁移到 RDS。
- Milvus 初期可在 ECS Docker 运行，数据量增长后再评估托管或独立实例。
- 使用 HTTPS。
- 生产环境 `.env` 不入库。

## 10. 测试策略

### 10.1 后端测试

使用 pytest。

必须覆盖：

- 登录成功和失败。
- 管理员、完整权限员工、通用权限员工的权限差异。
- 通用权限账号无法查看全量级内容。
- 内容发布生成版本。
- 下线内容不参与前台展示和 AI 检索。
- AI 未命中写入 `missed_questions`。
- 向量同步失败时内容仍可前台查看。

### 10.2 前端测试

使用 Vitest。

优先覆盖：

- 路由守卫。
- API 错误处理。
- 权限入口展示。
- 列表空状态。
- AI 未命中状态。

### 10.3 端到端测试

使用 Playwright。

首期至少保留以下 smoke tests：

1. 管理员登录后台并创建通用级内容。
2. 管理员发布内容后，通用权限员工可见。
3. 管理员发布全量级内容后，通用权限员工不可见。
4. 完整权限员工可以检索全量级内容。
5. AI 未命中时显示固定提示并写入后台列表。

## 11. 暂不引入的技术

| 技术 | 首期不引入原因 |
| --- | --- |
| LangChain | 当前 RAG 流程固定，自研 service 更清晰 |
| LangGraph | 首期没有多 Agent、状态机、人工审核工作流 |
| Celery | 索引同步规模小，先用同步流程和手动重试 |
| Redis | 首期没有强依赖缓存、分布式锁或分布式限流 |
| Elasticsearch | 当前以语义检索为主，MySQL + Milvus 足够 |
| Kubernetes | 部署复杂度超过 MVP 需要 |
| Nuxt | 没有 SSR 和 SEO 诉求 |
| 微服务 | 当前业务边界高度耦合，单体更稳 |
| 对象存储 OSS | 首期不做文件上传 |

## 12. 版本建议

以 2026-06-17 为基准，建议使用以下版本策略：

| 技术 | 建议 |
| --- | --- |
| Python | 3.13.x |
| Node.js | 24 LTS |
| MySQL | 8.4 LTS |
| Vue | 3.x |
| Vite | 当前稳定版，随 Vue 官方脚手架生成 |
| FastAPI | 当前稳定版，使用 Pydantic v2 |
| SQLAlchemy | 2.x |
| Milvus | 当前稳定 Standalone 版本 |

版本策略：

- 不追预发布版本。
- 不在 MVP 首期使用 Python 3.14 或 Node.js Current 线做生产基线。
- 前后端依赖都应提交 lockfile。
- 主要依赖升级应先跑后端测试、前端测试和 Playwright smoke tests。

## 13. 推荐仓库结构

```text
work4/
  backend/
  frontend/
  docs/
  memory-bank/
    architecture.md
    design-document.md
    tech-stack.md
    implementation-plan.md
    progress.md
  infra/
    milvus/
    nginx/
  AGENTS.md
  .env.example
  .gitignore
  .gitattributes
```

说明：

- `backend/` 放 FastAPI 服务。
- `frontend/` 放 Vue 应用。
- `memory-bank/` 放 Codex 开发前必须阅读的架构和产品设计上下文。
- `infra/` 放本地依赖服务和后续部署配置。
- `.env.example` 只放变量名和示例占位值，不放真实密钥。

## 14. 最终推荐

首期最合适的技术栈是：

```text
Vue 3 + TypeScript + Vite + Vue Router + Pinia + Axios + Element Plus
FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic + PyMySQL
MySQL 8.4 LTS + Milvus Standalone + PyMilvus
DashScope qwen-plus + text-embedding-v4
pytest + Vitest + Playwright
Nginx + ECS，后续可迁移 RDS
```

这套方案保留了 PRD 中已经确定的关键技术方向，同时避免过早引入重型编排和复杂中间件。它的重点不是“技术多”，而是让权限、版本、索引和 AI 回答边界可控、可测、可上线。

## 15. 官方参考资料

- Python 发布与版本状态：https://www.python.org/downloads/ 、https://devguide.python.org/versions/
- Node.js 发布线：https://nodejs.org/en/about/previous-releases
- Vue 官方文档：https://vuejs.org/guide/quick-start
- Vue TypeScript 指南：https://vuejs.org/guide/typescript/overview
- Pinia 官方文档：https://pinia.vuejs.org/
- FastAPI 官方文档：https://fastapi.tiangolo.com/
- FastAPI 版本与 Pydantic 说明：https://fastapi.tiangolo.com/deployment/versions/
- SQLAlchemy 官方文档：https://docs.sqlalchemy.org/
- Alembic 官方文档：https://alembic.sqlalchemy.org/
- MySQL 8.4 Release Notes：https://dev.mysql.com/doc/relnotes/mysql/8.4/en/
- MySQL 8.0 EOL 说明：https://dev.mysql.com/doc/relnotes/mysql/8.0/en/
- Milvus 官方文档：https://milvus.io/docs
- Milvus Docker Standalone：https://milvus.io/docs/install_standalone-docker-compose.md
- DashScope OpenAI-compatible 文档：https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
- DashScope Embedding 文档：https://www.alibabacloud.com/help/en/model-studio/embedding
- Playwright 官方文档：https://playwright.dev/
- pytest 官方文档：https://docs.pytest.org/
- Vitest 官方文档：https://vitest.dev/guide/
