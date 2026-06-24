# 企业话术智能检索与统一培训管理系统 MVP 架构记忆

## 当前运行形态
- 前端是一个 Vue 3 + TypeScript + Vite SPA，承载登录页、员工端 `/app` 和后台端 `/admin`，并通过 Pinia 保存会话状态、通过 Vue Router 守卫控制前后台入口。
- 后端是一个 FastAPI 单体服务，承载 REST API、认证授权、内容管理、员工内容读取、测验管理、RAG 索引和 AI 问答编排。
- MySQL 是唯一权威业务数据源；自动化测试使用 SQLite 临时库验证模型、迁移和 API 行为，不改变生产目标。
- Alembic 管理表结构，当前迁移链为 `0001_initial_schema` -> `0002_add_content_draft_fields` -> `0003_add_content_index_status` -> `0004_publish_revision_permission` -> `0005_quiz_update_policy` -> `0006_quiz_ai_generation_sets`。
- Milvus 通过后端集成边界访问；自动化测试使用内存假客户端，真实模式使用 PyMilvus `MilvusClient` 写入本地 Milvus，Milvus 只作为向量索引，不保存权威正文。
- DashScope 只能由后端调用；真实模式通过 OpenAI-compatible `/embeddings` 和 `/chat/completions` 调用，自动化测试使用假客户端或 `httpx.MockTransport`，不默认调用真实模型服务。

## 架构决策
- 后端保持 FastAPI 单体，不拆微服务，不引入 LangChain、LangGraph、Celery、Redis、Kubernetes 或对象存储。
- 数据访问采用同步 SQLAlchemy 2.x + PyMySQL，优先保证 MVP 事务一致性和实现直观性。
- 每次受保护请求都从数据库加载当前用户，禁用账号无法继续访问。
- 内容权限以后端为准：`general_user` 只能访问 `general`，`full_user` 和 `admin` 可访问 `general` 与 `full`。
- 员工端内容接口只返回已发布、未下线、当前用户可见的当前版本；草稿、历史版本和下线内容不对员工可见。
- 内容发布会生成不可变 `content_versions` 快照，并为当前版本生成 active `content_chunks`；旧 chunk 会被置为 inactive。
- 内容发布后会触发同步索引流程；索引成功写入 `vector_index_records` 并将 `contents.index_status` 置为 `synced`，索引失败不回滚发布内容，只将状态置为 `failed`。
- Milvus 只保存向量和过滤元数据，不保存权威正文；AI 回答前必须回查 MySQL 当前版本正文。
- RAG 回答先做问题 embedding，再按权限召回 Milvus 候选，随后从 MySQL 回查并再次过滤已发布、当前版本、active chunk 和用户权限。
- 2026-06-22 起 RAG 检索采用混合召回：每次问答同时执行 Milvus 向量召回和 MySQL 关键词召回，关键词路径检索当前版本标题、分类和 chunk 正文，并在 SQL 层先过滤已发布、active chunk、当前版本和当前用户权限；两路候选按分数融合去重后，再进入统一 MySQL 回查和来源摘要流程。
- 2026-06-22 起员工端 RAG 默认采用 10 秒内响应优先的极速回答策略：命中授权来源后，后端直接基于 MySQL 回查后的当前 chunk 生成简明来源摘要，不再等待生成模型长回答；响应中的 `usage.mode=fast_extractive` 标识该模式。生成模型集成仍保留，但不作为员工端当前默认回答路径。
- 未命中包括无候选、低于相似度阈值、MySQL 回查后无有效来源；未命中会返回固定提示并写入 `missed_questions`。
- MVP 不做对话持久化，不创建 `conversation_threads`、`conversation_messages`、`rag_answer_sources`。
- MVP 不持久化员工测验答题记录、分数、排行或统计。

## 已实现 API 边界
- `GET /health`：服务健康检查。
- `POST /api/auth/login`：账号密码登录，返回 JWT 和公开用户信息。
- `GET /api/auth/me`：返回当前登录用户。
- `GET /api/admin/ping`：管理员权限探针。
- `POST /api/admin/contents`：管理员创建内容草稿。
- `GET /api/admin/contents`：管理员内容列表，支持类型、状态、权限级别、分类和分页筛选。
- `GET /api/admin/contents/{content_id}`：管理员内容详情。
- `PATCH /api/admin/contents/{content_id}`：管理员编辑草稿字段，不改历史版本。
- `POST /api/admin/contents/{content_id}/publish`：发布或再发布内容，生成新版本和 active chunk。
- `POST /api/admin/contents/{content_id}/retry-index`：管理员重试当前内容索引同步。
- `POST /api/admin/contents/{content_id}/offline`：下线内容并禁用相关 chunk。
- `GET /api/admin/contents/{content_id}/versions`：管理员查看历史版本。
- `GET /api/app/must-reads` 与 `GET /api/app/must-reads/{content_id}`：员工最新必读列表和详情。
- `GET /api/app/scripts` 与 `GET /api/app/scripts/{content_id}`：员工基础话术、标准化话术列表和详情。
- `POST /api/admin/quiz-questions`、`GET /api/admin/quiz-questions`、`PATCH /api/admin/quiz-questions/{question_id}`：后台测验题管理。
- `POST /api/admin/quiz-questions/{question_id}/enable` 与 `/disable`：启用或禁用测验题。
- `GET /api/admin/quiz-generation-batches`：管理员查看 AI 候选题生成批次，追踪来源版本、模型、提示词版本、生成数量和失败原因。
- `GET /api/admin/quiz-sets`：管理员查看大更新专题测验包及其题目数量。
- `POST /api/admin/contents/{content_id}/versions/{version_id}/generate-quiz`：管理员在历史版本页手动补触发候选题生成；大更新版本可同步写入专题测验包。
- `GET /api/app/quiz`：员工获取当前权限内 5 到 10 道启用题。
- `POST /api/app/quiz/submit`：员工提交答案并即时返回解析，不落库答题历史。
- `POST /api/app/rag/ask`：员工提交 AI 问答，默认返回 10 秒内极速来源摘要或固定未命中提示。
- `GET /api/admin/missed-questions`：管理员查看未命中问题列表。
- `POST /api/admin/missed-questions/{question_id}/mark-handled`：管理员将未命中问题标记为已处理。
- `POST /api/admin/users`：管理员创建通用权限或完整权限员工账号。
- `GET /api/admin/users`：管理员分页查看账号列表；管理员账号在前端只读。
- `PATCH /api/admin/users/{user_id}`：管理员编辑员工展示名、账号类型、内容权限和启用状态。
- `POST /api/admin/users/{user_id}/reset-password`：管理员重置员工密码，只返回成功标志。
- `POST /api/admin/users/{user_id}/disable`：管理员禁用员工账号；禁用后登录和已有 token 请求均会被拒绝。
- `POST /api/admin/users/{user_id}/enable`：管理员重新启用员工账号；管理员账号仍不允许通过员工账号入口管理。

## 文件职责

### 根目录
- `.env.example`：安全环境变量占位，只列变量名和本地示例，不包含真实 API Key、数据库密码或 JWT 密钥。
- `.gitignore`：忽略 `.env`、虚拟环境、`node_modules`、构建产物、Python 缓存和 egg-info 等本地文件。
- `.gitattributes`：仓库文本属性和换行规则。
- `AGENTS.md`：项目开发约束、权限规则、必读上下文和 Git 规则。
- `README.md`：项目简介。

### 后端项目
- `backend/pyproject.toml`：后端包元数据、运行依赖、开发依赖、pytest 配置和 setuptools 包发现规则；包含 httpx 与 PyMilvus 运行依赖。
- `backend/app/__init__.py`：后端 Python 包标记。
- `backend/app/main.py`：FastAPI 应用工厂，注册统一错误处理、认证、管理员探针、内容、测验、RAG、未命中问题、账号管理路由和健康检查。

### 后端核心
- `backend/app/core/__init__.py`：核心模块包标记。
- `backend/app/core/config.py`：Pydantic Settings 配置入口，提供数据库、Milvus collection、DashScope、RAG 阈值、JWT 和测试假客户端默认值。
- `backend/app/core/errors.py`：统一应用错误类型和 JSON 错误响应形状。
- `backend/app/core/security.py`：Argon2 密码哈希/校验、JWT 生成和解析。

### 后端数据库与迁移
- `backend/app/db/__init__.py`：数据库模块包标记。
- `backend/app/db/base.py`：导出 SQLAlchemy `Base`，供模型和迁移共享。
- `backend/app/db/session.py`：创建 SQLAlchemy engine、session factory、请求级 `get_db` 依赖和 `session_scope`。
- `backend/alembic.ini`：Alembic 默认配置，默认指向本地 MySQL 占位 URL。
- `backend/alembic/env.py`：Alembic 迁移运行入口，加载 SQLAlchemy metadata；默认配置仍是占位 URL 时，从仓库根目录 `.env` 读取 `DATABASE_URL`，测试显式 URL 不被覆盖。
- `backend/alembic/versions/0001_initial_schema.py`：初始表结构迁移，创建用户、内容、版本、chunk、向量索引记录、测验题和未命中问题表。
- `backend/alembic/versions/0002_add_content_draft_fields.py`：为 `contents` 增加 `draft_summary`、`draft_body`、`draft_payload`，让草稿与已发布版本快照解耦。
- `backend/alembic/versions/0003_add_content_index_status.py`：为 `contents` 增加 `index_status`，持久化未同步、已同步和同步失败状态。
- `backend/alembic/versions/0004_add_publish_revision_and_version_permission.py`：为内容发布增加草稿修订号、已发布修订号和版本权限快照，支持发布幂等与历史权限追溯。
- `backend/alembic/versions/0005_quiz_update_policy.py`：为内容版本增加更新级别、变更摘要和题库动作，为测验题增加关联版本、来源、审核状态和待复核标记。
- `backend/alembic/versions/0006_quiz_ai_generation_sets.py`：新增 AI 候选题生成批次、专题测验包和专题包题目关联表，并为测验题增加生成批次、过期时间和抽题优先级字段。

### 后端领域与模型
- `backend/app/domain/__init__.py`：领域模块包标记。
- `backend/app/domain/enums.py`：账号类型、内容权限、内容类型、内容状态、索引状态、测验题状态和未命中问题状态枚举。
- `backend/app/models/__init__.py`：集中导入模型，确保 Alembic 和 `Base.metadata` 能发现表。
- `backend/app/models/base.py`：SQLAlchemy declarative base 和通用时间戳 mixin。
- `backend/app/models/user.py`：`users` 模型，包含账号身份、密码哈希、内容权限和启用状态。
- `backend/app/models/content.py`：`contents`、`content_versions`、`content_chunks`、`vector_index_records` 模型；`contents` 保存当前草稿和索引状态，`content_versions` 保存发布快照，`content_chunks` 为 RAG 索引候选，`vector_index_records` 记录 Milvus 索引元数据。
- `backend/app/models/quiz.py`：`quiz_questions`、`quiz_generation_batches`、`quiz_sets`、`quiz_question_set_items` 模型；题目可追踪生成批次、过期时间和抽题优先级，专题包只组织题目，不记录员工完成情况；仍不包含答题记录表。
- `backend/app/models/missed_question.py`：`missed_questions` 模型，保留提问时账号类型和内容权限快照。

### 后端 API、Schema 与服务
- `backend/app/api/__init__.py`：API 模块包标记。
- `backend/app/api/deps.py`：数据库依赖、当前用户依赖、管理员依赖、内容权限集合计算、无泄露权限错误和外部客户端依赖入口。
- `backend/app/api/routes/__init__.py`：路由模块包标记。
- `backend/app/api/routes/admin.py`：管理员权限探针。
- `backend/app/api/routes/auth.py`：登录接口和当前用户接口。
- `backend/app/api/routes/content.py`：管理员内容管理、发布后索引同步、重试索引和员工最新必读/话术读取接口；历史版本响应补充发布人展示名和权限展示字段。
- `backend/app/api/routes/quiz.py`：后台测验题管理接口和员工测验获取/提交接口。
- `backend/app/api/routes/rag.py`：员工 AI 问答接口，调用 RAG 编排服务并返回回答、来源或未命中提示。
- `backend/app/api/routes/missed_question.py`：后台未命中问题列表和标记已处理接口。
- `backend/app/api/routes/user.py`：后台员工账号创建、分页列表、编辑、密码重置、禁用和启用接口；全部依赖管理员鉴权。
- `backend/app/schemas/__init__.py`：schema 模块包标记。
- `backend/app/schemas/auth.py`：登录请求和登录响应模型。
- `backend/app/schemas/user.py`：用户创建、编辑、密码重置输入和公开用户响应模型；员工密码至少 8 位，并校验账号类型和内容权限组合。
- `backend/app/schemas/content.py`：内容创建、更新、管理员响应和分页响应模型，并承载类型相关字段校验。
- `backend/app/schemas/quiz.py`：测验题创建、更新和员工提交答案模型。
- `backend/app/schemas/rag.py`：员工 RAG 问题请求模型。
- `backend/app/services/__init__.py`：服务层包标记。
- `backend/app/services/content_service.py`：内容创建、更新、列表、发布、下线、历史版本、当前版本 chunk 和员工可见性查询规则。
- `backend/app/services/quiz_service.py`：测验题创建、更新、启停、列表、员工抽题和响应字典转换规则；后台响应包含关联内容标题和更新时间。
- `backend/app/services/rag_index_service.py`：内容切片、稳定 hash、当前版本 chunk 替换、embedding 调用、Milvus 写入和索引状态更新。
- `backend/app/services/rag_answer_service.py`：RAG 问答编排，负责问题 embedding、Milvus 向量召回、MySQL 关键词召回、候选融合去重、MySQL 来源回查、权限过滤、上下文生成和未命中处理。
- `backend/app/services/missed_question_service.py`：未命中问题记录、分页列表、响应转换和标记已处理。
- `backend/app/services/user_service.py`：员工账号查询、用户名冲突检查、密码哈希、角色/权限组合校验、编辑、密码重置、禁用和启用；拒绝普通账号管理入口操作管理员账号。

### 后端运维命令
- `backend/app/cli/__init__.py`：后端运维 CLI 包标记。
- `backend/app/cli/create_admin.py`：首个管理员创建/更新命令，从环境变量或交互输入读取账号信息，使用 Argon2 哈希密码并写入 MySQL；不负责员工账号或业务测试数据。

### 后端外部集成
- `backend/app/integrations/__init__.py`：外部集成模块包标记。
- `backend/app/integrations/dashscope.py`：DashScope 聊天/embedding 抽象、假客户端、真实 OpenAI-compatible HTTP 客户端、严格来源提示词、API Key 检查和超时/认证/响应错误标准化；真实请求不读取系统代理环境，避免本地代理导致 HTTPS 链路抖动。
- `backend/app/integrations/milvus.py`：Milvus collection、向量写入、检索和失效抽象；提供按余弦相似度评分的内存假客户端用于自动化测试，并提供基于 PyMilvus `MilvusClient` 的真实客户端用于本地/生产写入。

### 端到端测试后端
- `backend/app/e2e_fixture.py`：阶段 10 确定性夹具定义，创建三类固定测试账号、通用/全量内容、测验题和可控命中/未命中的假 DashScope/Milvus 客户端；发布内容仍复用正式 service 流程。
- `backend/e2e_server.py`：Playwright 专用后端入口，重建 `backend/tmp/phase10-e2e.db`、加载夹具、注入进程内共享假客户端并监听 `127.0.0.1:8010`；不得用于真实业务运行。

### 后端测试
- `backend/tests/conftest.py`：SQLite 临时库、SQLAlchemy session、FastAPI TestClient、用户和鉴权头夹具。
- `backend/tests/test_config.py`：配置默认值测试，确保测试环境不需要真实密钥。
- `backend/tests/test_health.py`：健康检查 API 测试。
- `backend/tests/test_errors.py`：统一错误响应和无堆栈泄露测试。
- `backend/tests/test_repository_guardrails.py`：阶段 0 文档和 `.env.example` 安全检查。
- `backend/tests/test_db_session.py`：数据库 session 生命周期测试。
- `backend/tests/test_domain_enums.py`：账号类型和内容权限输入校验测试。
- `backend/tests/test_migrations_phase2.py`：Alembic 升级、降级、表结构和非目标表缺失测试；新增迁移后降级验证目标为 `base`。
- `backend/tests/test_models_phase2.py`：用户唯一性、内容版本关系、chunk/vector 关系、测验题和未命中问题测试。
- `backend/tests/test_seed_guidance.py`：初始管理员种子说明测试。
- `backend/tests/test_security_phase3.py`：密码哈希、密码校验、JWT 生成解析和过期测试。
- `backend/tests/test_auth_api_phase3.py`：登录成功、登录失败、当前用户依赖和管理员依赖 API 测试。
- `backend/tests/test_permissions_phase3.py`：内容权限过滤辅助和无泄露权限错误测试。
- `backend/tests/test_admin_content_phase4.py`：管理员内容草稿、筛选分页、编辑、发布、再发布、历史版本、下线和 AI 候选 chunk 测试。
- `backend/tests/test_employee_content_phase5.py`：员工最新必读、标准话术列表/详情、排序和权限隔离测试。
- `backend/tests/test_quiz_phase5.py`：后台测验题管理、员工抽题、提交解析、不持久化答题历史和提交权限隔离测试。
- `backend/tests/test_integrations_phase6.py`：DashScope/Milvus 假客户端、配置边界、错误标准化和元数据过滤测试。
- `backend/tests/test_rag_index_phase6.py`：切片规则、稳定 hash、索引成功、索引失败和重试索引测试。
- `backend/tests/test_rag_phase6.py`：RAG 问题 embedding、权限过滤、低分未命中、MySQL 回查、API 成功/未授权/供应商不可用测试。
- `backend/tests/test_missed_questions_phase6.py`：未命中问题快照、后台列表、标记已处理和非管理员拒绝测试。
- `backend/tests/test_admin_users_phase9.py`：后台员工账号创建、列表、编辑、密码重置、禁用、启用、重复用户名、非管理员拒绝和管理员账号保护测试。
- `backend/tests/test_admin_support_phase9.py`：阶段 9 后台展示契约测试，覆盖测验关联内容/更新时间和历史版本发布人展示名。
- `backend/tests/test_e2e_fixture_phase10.py`：阶段 10 后端夹具准备测试，覆盖三类账号登录、跨权限内容/题目、确定性 RAG 命中和未命中、索引记录数量。
- `backend/tests/test_dashscope_http_phase11.py`：使用 `httpx.MockTransport` 验证真实 DashScope embedding/chat 请求、响应解析和供应商错误映射，不访问外网。
- `backend/tests/test_documentation_phase11.py`：检查本地开发、宝塔/ECS 部署和真实全链路手册包含阶段 11 必需配置与命令。
- `backend/tests/test_initial_admin_cli_phase11.py`：验证初始管理员 CLI 创建/更新、Argon2 密码哈希、管理员角色和重新启用行为。

### 前端
- `frontend/package.json`：前端依赖、脚本和 pnpm 包管理声明。
- `frontend/pnpm-lock.yaml`：前端依赖锁文件。
- `frontend/pnpm-workspace.yaml`：pnpm 11 构建脚本允许配置。
- `frontend/index.html`：Vite 应用 HTML 入口。
- `frontend/vite.config.ts`：Vite + Vue 插件、`@` alias 和本地开发 `/api` 代理配置。
- `frontend/vitest.config.ts`：Vitest jsdom 测试配置。
- `frontend/playwright.config.ts`：阶段 10 Playwright 配置，单 worker 启动专用 FastAPI 与 Vite 服务并使用 Chromium 执行冒烟测试。
- `frontend/tsconfig.json`：TypeScript 编译配置。
- `frontend/src/main.ts`：Vue 应用挂载入口，安装 Pinia 和 Router，并注入 API client 的 token 与 401 处理。
- `frontend/src/App.vue`：根据路由 meta 选择应用区域并渲染路由视图。
- `frontend/src/components/AppShell.vue`：全局 shell，提供移动/桌面横向溢出约束。
- `frontend/src/components/EmployeeLayout.vue`：员工端共享布局，展示 AI 问答入口、三个核心入口、当前用户和退出登录。
- `frontend/src/components/AdminLayout.vue`：后台共享布局，展示内容、测验、账号和未命中问题导航，仅管理员渲染。
- `frontend/src/components/AppState.vue`：共享空状态、加载状态、权限错误、服务错误和 AI 不可用状态文案。
- `frontend/src/components/CopyButton.vue`：共享复制按钮，封装剪贴板写入和成功/失败反馈。
- `frontend/src/router/index.ts`：登录、员工端和后台端路由；包含登录态守卫、管理员守卫、阶段 8 员工页面，以及阶段 9 内容列表/新建/编辑/历史、测验、账号和未命中真实页面路由。
- `frontend/src/stores/auth.ts`：Pinia 认证状态仓库，管理 token、用户身份、账号类型、内容权限级别、会话持久化和退出登录。
- `frontend/src/api/client.ts`：Axios API client、Bearer token 注入、401 认证错误回调和统一错误归一化。
- `frontend/src/api/auth.ts`：登录 API 封装，响应字段与后端 `LoginResponse` 对齐。
- `frontend/src/api/admin-content.ts`：后台内容 API 和 TypeScript 契约，覆盖列表筛选分页、详情、创建、编辑、发布、下线、历史版本和索引重试。
- `frontend/src/api/admin-quiz.ts`：后台测验题 API 和类型，覆盖列表、新建、编辑、启用和禁用。
- `frontend/src/api/admin-users.ts`：后台员工账号 API 和类型，覆盖列表、新建、编辑、密码重置、禁用和启用。
- `frontend/src/api/admin-missed-questions.ts`：后台未命中问题 API 和类型，覆盖状态筛选列表和标记已处理。
- `frontend/src/pages/LoginPage.vue`：登录页，包含账号密码表单、必填校验、登录 API 调用、成功跳转和通用失败提示。
- `frontend/src/pages/EmployeeHomePage.vue`：员工首页正文区域，承载员工共享布局下的今日入口提示。
- `frontend/src/pages/AdminHomePage.vue`：后台首页，只提供后台模块入口提示；具体业务由 `/admin/*` 子页面承载。
- `frontend/src/pages/admin/ContentListPage.vue`：后台内容列表，负责筛选、分页、状态标签、操作可见性、发布确认、下线确认和索引重试。
- `frontend/src/pages/admin/ContentEditorPage.vue`：后台内容新建/编辑表单，按内容类型生成结构化载荷，保存后返回内容列表。
- `frontend/src/pages/admin/ContentHistoryPage.vue`：后台历史版本页，展示版本号、标题、发布时间、发布人、权限和正文快照。
- `frontend/src/pages/admin/QuizQuestionsPage.vue`：后台测验题列表与内联编辑器，支持新建、编辑和启停。
- `frontend/src/pages/admin/UsersPage.vue`：后台账号列表与内联编辑器，支持员工账号新建、编辑、密码重置、禁用和启用；管理员账号只读。
- `frontend/src/pages/admin/MissedQuestionsPage.vue`：后台未命中问题列表，支持状态筛选和标记已处理，不包含统计看板。
- `frontend/src/styles/base.css`：全局基础样式、页面宽度约束，以及阶段 9 后台表格、筛选器、表单、状态标签、分页和响应式样式。
- `frontend/src/vite-env.d.ts`：Vite 类型声明。
- `frontend/tests/setup.ts`：Vitest DOM matcher setup。
- `frontend/tests/auth-store.test.ts`：认证状态持久化、账号身份和退出登录测试。
- `frontend/tests/router.test.ts`：基础路由解析、员工端认证守卫和后台管理员守卫测试。
- `frontend/tests/api-client.test.ts`：API base URL、错误归一化、Bearer token 注入和 401 处理测试。
- `frontend/tests/login-page.test.ts`：登录表单校验、登录成功跳转、通用失败提示和移动端布局约束测试。
- `frontend/tests/shared-ui.test.ts`：员工/后台布局、全局状态和复制反馈测试。
- `frontend/tests/app-shell.test.ts`：移动和桌面布局横向溢出约束测试。
- `frontend/tests/admin-content-phase9.test.ts`：后台内容筛选、分页、状态标签、操作入口、发布/下线/索引重试、编辑器字段和历史版本测试。
- `frontend/tests/admin-operations-phase9.test.ts`：后台测验题、员工账号和未命中问题页面的创建、编辑、启停、重置、禁用、筛选和无统计看板测试。
- `frontend/e2e/mvp-smoke.spec.ts`：阶段 10 浏览器冒烟测试，覆盖管理员发布、权限隔离、完整权限可见与 AI 检索、未命中回写和测验不持久化。

### 文档与基础设施
- `docs/phase-0-guardrails.md`：阶段 0 护栏、工作区边界、测试策略和外部服务测试边界。
- `docs/local-development.md`：从根目录配置 `.env`、安装依赖、启动 MySQL/Milvus、迁移、创建管理员、启动前后端和运行三类测试的完整说明。
- `docs/initial-admin.md`：初始管理员账号创建说明和可执行 CLI 命令，要求通过环境变量或交互输入提供密码。
- `docs/deployment-bt-ecs.md`：宝塔与 ECS 部署说明，明确前端静态 HTML、FastAPI 本地监听、Nginx 反向代理、MySQL、Milvus Docker 和 DashScope 后端配置边界。
- `docs/mvp-acceptance-checklist.md`：将 14 条 MVP 验收标准映射到后端、前端、Playwright 或真实环境手测证据。
- `infra/local-services.md`：本地 MySQL 和 Milvus 主机、端口、角色边界和启动检查。
- `memory-bank/design-document.md`：产品设计基线。
- `memory-bank/tech-stack.md`：技术栈推荐和架构约束。
- `memory-bank/implementation-plan.md`：阶段式实施计划；本轮按阶段 9 执行，未修改计划文件。
- `memory-bank/progress.md`：开发进度和验证记录。
- `memory-bank/architecture.md`：当前架构记忆文件。

## 本地 MySQL 验证记录
- 2026-06-17 已使用本地 MySQL 创建/复用 `weview_mvp` 并执行 Alembic `upgrade head`。
- 阶段 4/5 烟测数据包含 `phase45_admin`、`phase45_general`、`phase45_full` 三类账号，以及一条通用最新必读、一条全量标准话术和五道通用测验题。
- 阶段 4/5 烟测确认：通用用户能看到通用最新必读和通用测验题，看不到全量标准话术；完整权限用户能看到全量标准话术。
- 2026-06-22 已将本地 MySQL 升级到 `0004_publish_revision_permission`，确认 `contents.draft_revision`、`contents.published_draft_revision` 和 `content_versions.permission_level` 已存在；内容列表、员工内容、测验和 RAG 接口不再因 ORM/表结构不一致返回 500。
- 阶段 6 烟测确认：内容发布后索引状态为 `synced`，RAG 命中返回带来源的回答，低分未命中返回固定提示并写入后台未命中列表。
- 真实 Milvus 写入已验证：`localhost:19530` 可连接，`weview_content_chunks` collection 已创建/复用，阶段 6 索引同步流程写入 `content-4-version-4-chunk-4` 后立即检索命中。
- MySQL root 密码和任何真实密钥不得写入仓库；以上记录只保存库名、账号名和行为结果。

## 阶段 8 前端架构补充
- 员工端页面已经从阶段 7 的占位入口升级为可操作页面，当前覆盖首页 AI 提问、最新必读、标准话术、巩固测试和 AI 问答结果。
- `frontend/src/components/EmployeeLayout.vue`：员工端共享布局和全局 AI 提问表单；负责空问题提示、非空问题跳转 `/app/ask`、三入口导航、当前用户展示和退出登录。
- `frontend/src/pages/EmployeeHomePage.vue`：员工首页正文区域；承载阶段 8 的今日入口提示，具体 AI 表单由 `EmployeeLayout` 负责。
- `frontend/src/pages/app/MustReadListPage.vue`：员工最新必读列表页；加载 `/api/app/must-reads`，处理 loading、empty、service error，展示发布时间、生效时间和权限标签。
- `frontend/src/pages/app/MustReadDetailPage.vue`：员工最新必读详情页；加载 `/api/app/must-reads/{contentId}`，展示更新正文和调整要点，403 时清空旧详情并展示无权查看。
- `frontend/src/pages/app/ScriptsPage.vue`：员工话术列表页；加载 `/api/app/scripts`，按分类筛选，分区展示核心基础话术和标准化话术。
- `frontend/src/pages/app/ScriptDetailPage.vue`：员工话术详情页；按内容类型展示基础话术正文/要点或标准化话术场景、推荐说法、禁用说法、备注，并复用复制按钮。
- `frontend/src/pages/app/QuizPage.vue`：员工巩固测试页；加载 `/api/app/quiz`，本地记录选项，提交到 `/api/app/quiz/submit`，只展示即时解析，不持久化分数或历史。
- `frontend/src/pages/app/AiAnswerPage.vue`：员工 AI 问答结果页；读取路由 query 中的问题，调用 `/api/app/rag/ask`，展示命中回答、来源、复制按钮、固定未命中文案或 AI 不可用状态。
- `frontend/src/api/content.ts`：员工端内容 API 封装，包含最新必读、话术列表和详情的 TypeScript 类型与请求函数。
- `frontend/src/api/quiz.ts`：员工端测验 API 封装，包含题目、提交 payload 和提交结果类型。
- `frontend/src/api/rag.ts`：员工端 RAG API 封装，包含回答来源和命中/未命中响应类型。
- `frontend/src/utils/format.ts`：前端展示格式工具，负责日期时间截断、权限标签、内容类型标签和 AI 来源详情链接生成。
- `frontend/vite.config.ts`：除 Vue 插件和 `@` alias 外，新增 dev server `/api` 代理；默认转发到 `http://127.0.0.1:8000`，可通过 `VITE_API_PROXY_TARGET` 覆盖。
- `.env.example`：前端示例配置已改为 `VITE_API_BASE_URL=/api` 和 `VITE_API_PROXY_TARGET=http://127.0.0.1:8000`，避免本地开发跨域和 API 前缀错位。
- `frontend/tests/employee-content-phase8.test.ts`：覆盖最新必读和话术页面的列表、详情、权限错误、分类筛选和复制行为。
- `frontend/tests/employee-quiz-ai-phase8.test.ts`：覆盖员工首页提问、巩固测试、AI 命中、未命中和不可用状态。
- `docs/frontend-testing-manual.md`：真实全链路前端操作手册，要求除首个管理员外全部数据经管理员前端和 FastAPI 写入真实 MySQL/Milvus，并覆盖后台、员工权限、版本、测验、真实 AI 命中/未命中和只读落库核验。
- `docs/seed-phase8-manual-data.py`：本地手测数据辅助脚本，从环境变量读取数据库连接和测试密码，创建/更新三类账号、员工端内容和 5 道测验题；不包含真实密码或 API Key。

## 阶段 9 后台架构补充
- 后台继续位于同一个 Vue SPA 和同一个 FastAPI 单体中，没有新增服务或中间件。
- 前端后台页面负责交互和展示；管理员权限、员工账号可管理范围、密码哈希、内容状态和索引操作合法性以后端为最终边界。
- 后台请求按内容、测验、账号、未命中问题拆分为四个 API 模块，页面不直接拼 Axios 配置，继续复用 Bearer token 注入、401 清理会话和统一错误归一化。
- 账号管理是阶段 9 唯一新增的后端业务边界。它只管理员工账号，不承担管理员初始化或管理员密码维护；管理员账号继续由运维流程创建和维护。
- 密码重置由管理员输入新临时密码，后端只保存 Argon2 哈希并返回 `{"reset": true}`；前端不会读取或展示数据库密码哈希。
- 后台内容发布继续调用既有同步索引流程；发布成功但索引失败时，内容保持可见，后台提示 AI 检索暂不可用并提供重试入口。
- 历史版本的正文、标题和结构化载荷来自不可变 `content_versions`；当前版本表尚未保存权限快照，所以历史页显示的权限级别暂取 `contents.permission_level` 当前值。
- 前端可展示 `syncing` 标签作为未来兼容值，但当前数据库 `IndexStatus` 只持久化 `not_synced`、`synced`、`failed`。
- 自动化验证覆盖后端 API/服务、前端组件和生产构建；2026-06-18 已使用内置 Browser 和临时 SQLite 后端完成阶段 9 管理员登录、内容、历史、测验、账号和未命中页面烟测，浏览器控制台无 warning/error。
- 599px 窄屏下后台业务页无全局横向溢出，宽表格由页面内部滚动容器承载；后台首页的深色导航区域偏高，是已知视觉优化点。
- 本次 Browser 烟测仍不是阶段 10 的正式 Playwright 端到端测试，后续需保留确定性夹具和可重复执行的自动化流程。

## 当前验证基线
- 后端：`..\.venv\Scripts\python.exe -m pytest`，当前 `129 passed`。
- 前端单测：`corepack.cmd pnpm test:unit`，当前 `63 passed`。
- 前端构建：`corepack.cmd pnpm build`，当前构建成功。
- Playwright：`corepack.cmd pnpm test:e2e`，当前 `5 passed`。

## 阶段 10 端到端架构补充
- 自动化端到端环境与真实手测环境严格分离。阶段 10 使用专用 SQLite 和进程内假客户端，以获得可重复、无外网依赖的权限与业务流程验证。
- Playwright 通过真实浏览器、Vite 代理和 FastAPI HTTP API 操作系统，不 mock 前端 API 模块。
- E2E 后端启动时重建专用数据库并加载固定夹具；测试结束后不写入真实 MySQL 或 Milvus。
- 发布和 RAG 请求必须共享同一个假 Milvus 实例，否则发布请求写入的内存向量无法被后续问答请求召回。
- 假 Milvus 默认按余弦相似度评分，阶段 10 使用反向 query embedding 制造稳定低分未命中；业务服务仍使用正式相似度阈值和 MySQL 回查规则。
- Vitest 仅发现 `frontend/tests/**/*.test.ts`，Playwright 仅发现 `frontend/e2e`，两个运行器互不收集对方测试。
- 真实 MySQL、真实 Milvus、真实 DashScope 的全链路验收不由阶段 10 假客户端替代，必须按完整前端手测说明执行。

## 阶段 11 文档与真实外部服务补充
- `DashScopeHttpClient` 使用 `DASHSCOPE_BASE_URL` 拼接 `/embeddings` 和 `/chat/completions`，请求头只在后端携带 Bearer API Key。
- embedding 请求使用 `text-embedding-v4` 和 `encoding_format=float`；2026-06-18 本机真实响应维度为 1024。
- chat 请求使用 `qwen-plus`，system prompt 要求只能依据已授权来源，不得补充未提供业务结论；返回值只暴露标准化回答和 token usage。
- 自动化测试通过注入 `httpx.Client(MockTransport)` 验证 HTTP 契约，不消耗真实模型额度。
- Alembic 默认占位 URL 会被根目录 `.env` 中的 `DATABASE_URL` 替换；测试提供的 SQLite URL 和显式非占位 URL保持优先。
- 首个管理员由运维 CLI 直接写 MySQL，这是启动引导例外；员工、内容、测验、发布、索引和未命中测试数据必须经前端/API 创建。
- 前端生产部署是静态 `dist`，FastAPI 监听 `127.0.0.1` 并由 Nginx/宝塔代理 `/api`；SQLAlchemy 只是 ORM，MySQL 仍是唯一业务数据库。
- 真实手测应为 `text-embedding-v4` 使用新 Milvus collection，避免与旧 3 维假向量 collection 冲突。
- 2026-06-18 已完成真实浏览器链路：管理员前端创建账号和内容，FastAPI 写入 MySQL，发布后 `text-embedding-v4` 生成 1024 维向量并写入 `weview_content_chunks_codex_real_v4_20260618`，通用员工问答由 Milvus 命中、MySQL 回查和 `qwen-plus` 生成带来源回答；无关问题写入后台未命中列表。
## 2026-06-23 测验题与内容更新联动补充

- Alembic 迁移链已扩展到 `0005_quiz_update_policy`，在不新增员工答题记录表的前提下完成第一阶段题库稳态增强。
- `content_versions` 现在同时保存 `version_no` 与 `update_level`：`version_no` 表示第几次发布，`update_level` 表示本次发布影响级别，二者互不替代。新增字段包括 `update_level`、`change_summary`、`quiz_action`、`ai_suggested_update_level`、`ai_suggestion_reason`。
- `quiz_questions` 现在支持绑定发布版本与审核流转，新增 `related_version_id`、`source_type`、`review_status`、`needs_review`、`review_reason`。人工题默认 `source_type=manual`、`review_status=approved`，AI 生成题后续必须保持“候选/待审核/禁用”边界，不得直接进入员工端。
- 内容发布接口 `POST /api/admin/contents/{content_id}/publish` 保持老调用兼容，同时可接收发布参数：`update_level`、`change_summary`、`quiz_action` 与 AI 建议字段。若未显式传 `quiz_action`，后端按更新级别推导：`minor -> none`，`medium -> review_related`，`major -> generate_pack`。
- 内容发布为 `medium` 或 `major` 时，后端会把 `related_content_id` 指向该内容的既有题目标记为 `needs_review=true`，并写入 `review_reason`。`minor` 不强制影响题库。
- 员工端抽题规则已收紧为：仅返回 `status=enabled`、`review_status=approved`、`needs_review=false`、当前账号权限内的题；如果题目绑定了内容，则关联内容必须仍为 `published`、有当前版本且当前用户可见。内容下线或权限变更后，绑定题不会绕过内容权限暴露给员工。
- 后台内容列表发布时会要求管理员输入本次更新级别与变更摘要；后台历史版本页展示更新级别、题库动作和变更摘要；后台测验题管理页可查看和编辑关联版本、来源、审核状态、待复核标记与复核原因。
- 当前版本的更新级别已作为可见业务信息暴露给管理员和员工：后台内容列表在版本右侧展示“更新级别”，员工端最新必读、标准话术列表与详情页展示“小更新/中更新/大更新”，AI 问答来源卡片也展示来源版本的更新级别，避免使用者只看到内容而不知道本次更新影响范围。

## 2026-06-23 测验题第二/三阶段补充

- Alembic 迁移链已继续扩展到 `0006_quiz_ai_generation_sets`：`quiz_generation_batches` 记录 AI 候选题生成批次，`quiz_sets` 与 `quiz_question_set_items` 组织大更新专题测验包；`quiz_questions` 增加 `generation_batch_id`、`expires_at`、`priority`。
- 内容发布接口不再同步调用 DashScope 生成候选题，避免大更新发布被模型超时拖成前端“假失败”。发布响应会返回 `quiz_generation_status`：`not_required`、`pending`、`completed` 或 `failed`；其中 `pending` 表示内容已发布且题库候选题可在历史版本页手动生成。
- AI 生成题默认 `source_type=ai_generated`、`review_status=pending_review`、`status=disabled`，并绑定来源内容、来源版本和生成批次。管理员必须在测验题管理页审核通过并启用后，员工端才可能抽到该题。
- `medium` 更新默认请求生成 3 道候选题，优先级为 50；`major` 更新默认请求生成 5 道候选题，优先级为 100，并自动创建或复用该版本的大更新专题测验包。
- 员工端抽题仍不记录答题历史，但过滤条件进一步收紧为：启用、审核通过、无需复核、未过期、当前用户权限内、绑定内容仍发布且可见；排序按 `priority desc, id asc`，使已审核启用的大更新专题题优先进入本次 5-10 道巩固测试。
- 后台新增 `GET /api/admin/quiz-generation-batches`、`GET /api/admin/quiz-sets` 和 `POST /api/admin/contents/{content_id}/versions/{version_id}/generate-quiz`。前端历史版本页提供“生成候选题”入口，测验题管理页展示专题包、生成批次、过期时间和抽题优先级。
- 后台测验题新增显式审核动作：`POST /api/admin/quiz-questions/{question_id}/approve` 会同时将题目置为“审核通过、启用、无需复核”，`POST /api/admin/quiz-questions/{question_id}/reject` 会将题目置为“已拒绝、禁用”。前端对未审核题不再展示普通“启用”，而展示“审核通过并启用 / 驳回”，避免出现“启用但仍待审核”的误导性操作。
- 内容下线时会同步将关联专题测验包置为 `inactive`。员工端此前已按关联内容发布状态过滤题目；该联动用于让后台专题包状态与实际员工端可见性一致，避免管理员误以为下线内容的专题包仍在员工端生效。

## 2026-06-24 测验题来源失效联动补充

- 测验题后台响应现在包含 `source_valid` 与 `source_invalid_reason`，用于展示题目绑定来源是否仍可上线。来源失效原因包括源内容不存在、源内容已下线、源内容未发布、源内容无当前版本、源版本已失效和专题包已停用。
- 后端将“来源有效性”作为审核通过和启用题目的硬约束：`approve` 与 `enable` 操作会校验关联内容仍为已发布、关联版本仍是内容当前版本、关联专题包未停用；校验失败返回 `quiz_source_invalid`，避免前端状态滞后或多人并发操作导致旧题上线。
- 员工端抽题与提交校验进一步收紧：如果题目绑定了 `related_version_id`，该版本必须等于关联内容的 `current_version_id`。因此内容重新发布后，旧版本题即使仍是已审核/启用，也不会进入员工巩固测试或提交解析。
- 内容下线时不再只停用专题包，还会同步处理关联题目：草稿或待审核题自动置为 `rejected + disabled`，已通过题置为 `disabled + needs_review`，并写入“源内容已下线”的复核/驳回原因。
- 内容重新发布新版本时，旧版本专题包会自动置为 `inactive`；绑定旧版本的草稿或待审核题自动驳回并禁用，已通过旧题禁用并标记待复核，复核原因记录旧版本已被新版本替代。
- 后台测验题管理页新增“来源状态”列。来源失效题不再显示“审核通过并启用”或普通“启用”操作，只保留安全的“驳回”清理动作；审核、驳回、启用和禁用按钮增加行级处理中状态，减少连续点击和列表刷新造成的交互漂移。
