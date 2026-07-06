# 企业话术智能检索与统一培训管理系统 MVP 架构记忆

## 当前运行形态
- 前端是一个 Vue 3 + TypeScript + Vite SPA，承载登录页、员工端 `/app` 和后台端 `/admin`，并通过 Pinia 保存会话状态、通过 Vue Router 守卫控制前后台入口。
- 后端是一个 FastAPI 单体服务，承载 REST API、认证授权、内容管理、员工内容读取、测验管理、RAG 索引和 AI 问答编排。
- MySQL 是唯一权威业务数据源；自动化测试使用 SQLite 临时库验证模型、迁移和 API 行为，不改变生产目标。
- Alembic 管理表结构，当前迁移链为 `0001_initial_schema` -> `0002_add_content_draft_fields` -> `0003_add_content_index_status` -> `0004_publish_revision_permission` -> `0005_quiz_update_policy` -> `0006_quiz_ai_generation_sets` -> `0007_department_scope`。
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
- 2026-07-06 极速回答提取逻辑修正：修复了 `fast_extractive` 模式下“由于合并前序相邻上下文导致总是返回文档开头”的问题。`build_fast_answer` 现在优先基于实际命中的核心片段 (`hit_texts`) 进行提取，同时在精简阶段额外过滤掉“摘要：”前缀，确保返回内容精确聚焦于用户提问相关区域。
- 未命中包括无候选、低于相似度阈值、MySQL 回查后无有效来源；未命中会返回固定提示并写入 `missed_questions`。
- MVP 不做对话持久化，不创建 `conversation_threads`、`conversation_messages`、`rag_answer_sources`。
- MVP 不持久化员工测验答题记录、分数、排行或统计。

## 已实现 API 边界
- `GET /health`：服务健康检查。
- `POST /api/auth/login`：账号密码登录，返回 JWT 和公开用户信息。
- `GET /api/auth/me`：返回当前登录用户。
- `GET /api/admin/ping`：管理员权限探针。
- `POST /api/admin/contents`：管理员创建内容草稿。
- `POST /api/admin/content-import/parse`：管理员上传 `.docx`/`.pdf` 并解析为单条草稿和可选拆解候选；只返回解析结果，不创建内容、不发布、不写入向量索引。
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
- `backend/pyproject.toml`：后端包元数据、运行依赖、开发依赖、pytest 配置和 setuptools 包发现规则；包含 httpx、PyMilvus、python-multipart、python-docx 与 PyMuPDF 运行依赖。
- `backend/app/__init__.py`：后端 Python 包标记。
- `backend/app/main.py`：FastAPI 应用工厂，注册统一错误处理、认证、管理员探针、内容、内容导入解析、测验、RAG、未命中问题、账号管理路由和健康检查。

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
- `backend/app/api/routes/content_import.py`：管理员 Word/PDF 导入解析接口，接收 multipart 文件、校验内容类型和解析模式，并复用后端管理员鉴权与 DashScope 依赖。
- `backend/app/api/routes/quiz.py`：后台测验题管理接口和员工测验获取/提交接口。
- `backend/app/api/routes/rag.py`：员工 AI 问答接口，调用 RAG 编排服务并返回回答、来源或未命中提示。
- `backend/app/api/routes/missed_question.py`：后台未命中问题列表和标记已处理接口。
- `backend/app/api/routes/user.py`：后台员工账号创建、分页列表、编辑、密码重置、禁用和启用接口；全部依赖管理员鉴权。
- `backend/app/schemas/__init__.py`：schema 模块包标记。
- `backend/app/schemas/auth.py`：登录请求和登录响应模型。
- `backend/app/schemas/user.py`：用户创建、编辑、密码重置输入和公开用户响应模型；员工密码至少 8 位，并校验账号类型和内容权限组合。
- `backend/app/schemas/content.py`：内容创建、更新、管理员响应和分页响应模型，并承载类型相关字段校验。
- `backend/app/schemas/content_import.py`：Word/PDF 导入解析响应模型，包含单条草稿、拆解候选、原始文本、解析方式、逐页选择信息和警告。
- `backend/app/schemas/quiz.py`：测验题创建、更新和员工提交答案模型。
- `backend/app/schemas/rag.py`：员工 RAG 问题请求模型。
- `backend/app/services/__init__.py`：服务层包标记。
- `backend/app/services/content_service.py`：内容创建、更新、列表、发布、下线、历史版本、当前版本 chunk 和员工可见性查询规则。
- `backend/app/services/document_extractors.py`：DOCX/PDF 本地解析、表格文本化、PDF 页面渲染、OCR 页选择和本地/OCR 文本质量评分。
- `backend/app/services/document_import_service.py`：导入解析编排，负责文件大小、扩展名、MIME、页数和 OCR 页数限制，并将解析失败映射为业务错误。
- `backend/app/services/document_structuring_service.py`：调用 DashScope 文本结构化能力，把原始解析文本整理为内容草稿和拆解候选，并提供保守兜底拆分。
- `backend/app/services/quiz_service.py`：测验题创建、更新、启停、列表、员工抽题和响应字典转换规则；后台响应包含关联内容标题和更新时间。
- `backend/app/services/rag_index_service.py`：内容切片、长文本检索窗口拆分、稳定 hash、当前版本 chunk 替换、embedding 调用、Milvus 写入和索引状态更新。
- `backend/app/services/rag_answer_service.py`：RAG 问答编排，负责问题 embedding、Milvus 向量召回、MySQL 关键词召回、候选融合去重、MySQL 来源回查、权限过滤、相邻 chunk 上下文生成和未命中处理。
- `backend/app/services/missed_question_service.py`：未命中问题记录、分页列表、响应转换和标记已处理。
- `backend/app/services/user_service.py`：员工账号查询、用户名冲突检查、密码哈希、角色/权限组合校验、编辑、密码重置、禁用和启用；拒绝普通账号管理入口操作管理员账号。

### 后端运维命令
- `backend/app/cli/__init__.py`：后端运维 CLI 包标记。
- `backend/app/cli/create_admin.py`：首个管理员创建/更新命令，从环境变量或交互输入读取账号信息，使用 Argon2 哈希密码并写入 MySQL；不负责员工账号或业务测试数据。

### 后端外部集成
- `backend/app/integrations/__init__.py`：外部集成模块包标记。
- `backend/app/integrations/dashscope.py`：DashScope 聊天/embedding/OCR/内容导入结构化抽象、假客户端、真实 OpenAI-compatible HTTP 客户端、严格来源提示词、API Key 检查和超时/认证/响应错误标准化；真实请求不读取系统代理环境，避免本地代理导致 HTTPS 链路抖动。
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
- `backend/tests/test_dashscope_http_phase11.py`：使用 `httpx.MockTransport` 验证真实 DashScope embedding/chat/OCR/内容导入结构化请求、响应解析和供应商错误映射，不访问外网。
- `backend/tests/test_content_import_phase12.py`：Word/PDF 导入解析接口测试，覆盖管理员权限、文件类型拒绝、DOCX 文本/表格、DOCX 快速模式跳过图片 OCR、强制 DOCX 图片 OCR、PDF 增强 OCR、解析不落内容表和供应商异常映射。
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
- `frontend/src/api/admin-content.ts`：后台内容 API 和 TypeScript 契约，覆盖列表筛选分页、详情、创建、编辑、发布、下线、历史版本、索引重试和 Word/PDF 导入解析。
- `frontend/src/api/admin-quiz.ts`：后台测验题 API 和类型，覆盖列表、新建、编辑、启用和禁用。
- `frontend/src/api/admin-users.ts`：后台员工账号 API 和类型，覆盖列表、新建、编辑、密码重置、禁用和启用。
- `frontend/src/api/admin-missed-questions.ts`：后台未命中问题 API 和类型，覆盖状态筛选列表和标记已处理。
- `frontend/src/pages/LoginPage.vue`：登录页，包含账号密码表单、必填校验、登录 API 调用、成功跳转和通用失败提示。
- `frontend/src/pages/EmployeeHomePage.vue`：员工首页正文区域，承载员工共享布局下的今日入口提示。
- `frontend/src/pages/AdminHomePage.vue`：后台首页，只提供后台模块入口提示；具体业务由 `/admin/*` 子页面承载。
- `frontend/src/pages/admin/ContentListPage.vue`：后台内容列表，负责筛选、分页、状态标签、操作可见性、发布确认、下线确认和索引重试。
- `frontend/src/pages/admin/ContentEditorPage.vue`：后台内容新建/编辑表单，按内容类型生成结构化载荷；新建时可上传 Word/PDF 解析并填入表单，也可保存勾选的拆解候选为草稿。
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
- `frontend/tests/admin-content-phase9.test.ts`：后台内容筛选、分页、状态标签、操作入口、发布/下线/索引重试、编辑器字段、Word/PDF 导入和历史版本测试。
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

## 2026-06-25 部门范围权限补充

- 在不推翻既有 `permission_level` 的前提下，权限模型扩展为“横向归属范围 + 纵向账号等级”两层过滤：`scope_type` 负责内容是否全公司通用或限定某个部门，`permission_level` 继续负责通用级/全量级敏感度过滤。
- 新增 `departments` 表，员工账号 `users.department_id` 可选关联一个启用部门。未分配部门的员工仍可登录，但只能依账号等级查看 `scope_type=global` 的内容；管理员不受部门过滤限制。
- `contents`、`content_versions`、`content_chunks` 均新增 `scope_type` 与 `department_id`。发布时会把内容当前范围快照到版本和 chunk，保证历史版本、RAG chunk 与当前内容范围有一致来源。
- 存量内容迁移默认写入 `scope_type=global`、`department_id=null`，存量账号默认 `department_id=null`，因此迁移后不会突然把旧内容隐藏，也不会强制老账号必须立刻补部门。
- 内容范围合法性由后端统一校验：全公司通用内容不得绑定部门；部门限定内容必须绑定一个启用部门。前端展示和隐藏入口只做交互辅助，不能替代后端权限判断。
- 员工端最新必读、标准话术、详情、AI 来源和巩固测试均执行统一过滤：先按 `scope_type/department_id` 判断部门范围，再按 `permission_level` 判断账号等级。全公司通用内容仍按账号等级可见；部门限定内容只对同部门且等级足够的员工可见。
- RAG 混合检索两条路径都纳入部门范围：Milvus metadata 增加 `scope_type`/`department_id` 过滤，MySQL 关键词召回和最终正文回查也再次执行 scope + permission 双重校验。Milvus 仍不是权威来源，AI 回答前必须回查 MySQL。
- 测验题中绑定内容的题目跟随关联内容当前范围和权限可见性；非绑定内容的人工通用题暂不新增部门字段，仍按题目自身 `permission_level` 控制，避免把题库一次性复杂化。
- 后台新增部门管理 API 与页面；账号管理页面可给员工分配部门；内容编辑与列表页面可设置/展示“全公司通用”或“限定部门”。员工端页面展示可见范围，减少员工误解“为什么我看到了/看不到这条内容”。
- 本轮验证基线：后端 `python -m pytest backend\tests -q` 通过；前端 `pnpm run test:unit` 为 `65 passed`；前端 `pnpm run build` 通过。

## 2026-06-29 Bugfix/UX 最小改动补充

- 内容分类不新增数据表，仍复用 `contents.category` 作为唯一分类字段。后端新增 `GET /api/admin/content-categories`，仅管理员可访问，从历史内容中按最近更新读取、去空格、去空值、去重并最多返回 100 个分类；前端内容编辑页将固定分类常量与历史分类合并，通过原生 `input + datalist` 提供可选可输的分类建议。
- 员工端最新必读响应补充 `category` 字段；前端最新必读页在当前可见内容内提供分类和可见范围筛选，并先采用前端分页，每页 10 条。标准话术页保持后端现有分类筛选，列表展示改为每组默认 10 条并支持“查看更多/收起”。
- 前端统一通过 `formatDateTime` 使用 `Intl.DateTimeFormat` 和 `Asia/Shanghai` 输出北京时间；后端返回无时区的 ISO 字符串时，前端按 UTC 兜底解析后转北京时间，空值或非法时间显示 `-`。
- 员工端测验接口扩展为 `GET /api/app/quiz?mode=latest|review&category=`。`latest` 保持默认兼容，但在同等优先级下优先关联最近发布内容的题；`review` 在当前用户权限和部门范围内取有效题，并可按关联内容 `category` 过滤。题目响应带出 `related_content_category`，供前端复习模式分类筛选。
- 巩固测试前端默认“跟进最新”，新增“复习旧内容”模式、答题进度、未答完提示、提交后锁定选项和“重新抽题”；仍不新增员工答题历史、分数、排行或统计表。
- 后台账号管理和测验题管理复用已有分页 API：账号、题干、专题测验包分别维护页码和总数。重置密码表单新增面板内错误 `resetError`，短密码会直接提示“新密码至少 8 位”，避免用户误以为按钮无响应。
- 本轮验证基线：后端 `..\.venv\Scripts\python.exe -m pytest tests -q` 通过；前端 `corepack.cmd pnpm test:unit` 为 `72 passed`；前端 `corepack.cmd pnpm build` 通过。

## 2026-06-30 巩固测试抽题随机化补充

- 员工端测验接口 `GET /api/app/quiz` 新增可选 `refresh_seed` 查询参数；不传 seed 时继续沿用原固定排序，保证旧调用兼容。
- 传入 `refresh_seed` 时，后端先按既有状态、权限、部门范围、过期时间、关联内容发布状态和当前版本有效性过滤，再按每个权限层最多 100 道候选题进入 Python 层抽样，不使用数据库 `ORDER BY RAND()`。
- 抽样策略为“分层优先 + 层内稳定随机”：组间按 `priority desc`、关联内容当前版本发布时间或题目更新时间、版本/批次 id 排序；组内按 `sha256(refresh_seed + question.id)` 稳定打散。同一 seed 与同一候选集结果可复现，不同 seed 在同组内尽量变化。
- `latest` 模式仍保留现有权限分路：通用账号只抽通用题；完整权限账号和管理员优先保留 1 道全量题，再用通用题补足，不足时继续补全量题。`review` 模式继续支持分类过滤。
- 前端 `QuizPage` 每次首次加载、切换模式、切换分类和点击“重新抽题”都会生成新的 `refresh_seed`，提交答案仍只按当前题目 id 提交，提交后选项锁定；按钮旁增加“题库较少时可能抽到相同题目”的弱提示。

## 2026-06-30 Word/PDF 导入解析与 OCR 补充

- 后台内容新建页新增 Word/PDF 导入区，管理员先选择内容类型，再上传 `.docx` 或 `.pdf`，可选快速解析、增强解析和强制 OCR。解析结果只填入当前表单或作为候选草稿保存，不自动发布，不进入员工端，不写入 Milvus。
- 新增 `POST /api/admin/content-import/parse`，仅管理员可访问。接口接收 multipart 文件，拒绝 `.doc`、`.wps`、图片等非本期范围文件，默认 20MB 文件上限、80 页 PDF 上限、30 页 OCR 上限。
- DOCX 解析优先使用 `python-docx` 本地提取段落和表格；快速模式下若段落/表格已抽取到正文，则跳过内嵌图片 OCR 并返回“快速解析未执行图片 OCR”的核对警告，避免普通 Word 导入被图片 OCR 拖到前端超时。只有勾选强制 OCR 或 DOCX 无本地正文时，才会调用 `qwen-vl-ocr-2025-11-20` 识别内嵌大图并合并到原始文本。PDF 解析使用 PyMuPDF 本地抽取文本，增强模式或低质量文本页会渲染页面图片并 OCR，再按质量评分选择本地文本或 OCR 文本。
- DOCX 内嵌图片 OCR 属于增强能力，不是本地文本抽取的硬依赖。若强制 OCR 时图片 OCR 失败，接口仍返回草稿并给出“图片 OCR 失败”的核对警告。若 `qwen-plus` 结构化整理失败或返回非 JSON，接口也返回基于本地解析文本的保守草稿，并提示管理员人工核对字段，避免把可编辑正文丢成 503。
- DashScope 集成扩展为 embedding、chat、OCR 和内容导入结构化四类调用。OCR 使用 `qwen-vl-ocr-2025-11-20`，结构化整理仍用 `qwen-plus` 的 JSON 输出，提示词要求尽量保留原文，不凭空补充业务事实。
- 结构化服务始终返回 `single_draft`，并在文档较长或模型返回多段时提供 `split_suggestions`。前端高/中置信候选默认勾选，管理员选择权限级别和可见范围后，可点击“保存选中为草稿”，仍复用现有 `POST /api/admin/contents`，由既有内容校验保证标准化话术和最新必读必填字段。
- 前端导入解析请求在 `frontend/src/api/admin-content.ts` 单独使用 120 秒 timeout，避免复用全局 15 秒 API 超时导致“请求等待时间较长”提前返回；后端仍负责文件大小、页数和 OCR 页数边界控制。
- 内容发布索引补充长文本检索窗口：逻辑 chunk 超过约 1100 字时会按 180 字重叠拆成多个 active chunk，每个窗口保留标题、分类、摘要等上下文前缀；短内容保持原有单 chunk 行为。AI 回答从命中 chunk 回查时，会在权限和范围过滤后拼接同内容相邻 chunk，减少长文命中局部导致回答断裂。
- 本轮验证基线：后端 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_content_import_phase12.py backend\tests\test_dashscope_http_phase11.py backend\tests\test_rag_index_phase6.py backend\tests\test_rag_phase6.py` 为 `49 passed`；前端 `corepack.cmd pnpm exec vitest run tests/admin-content-phase9.test.ts` 为 `14 passed`；前端 `corepack.cmd pnpm run build` 通过。

## 2026-07-01 Word/PDF 导入修订

- DashScope 模型和超时已拆为任务级配置：`DASHSCOPE_CHAT_MODEL`、`DASHSCOPE_STRUCTURE_MODEL`、`DASHSCOPE_QUIZ_MODEL`、`DASHSCOPE_OCR_MODEL`、`DASHSCOPE_VISION_MODEL` 以及 `DASHSCOPE_HTTP_TIMEOUT_SECONDS`、`DASHSCOPE_IMPORT_TIMEOUT_SECONDS`、`DASHSCOPE_OCR_TIMEOUT_SECONDS`、`DASHSCOPE_QUIZ_TIMEOUT_SECONDS`。默认结构化和候选题生成使用 `qwen-plus`，OCR 使用 `qwen-vl-ocr-2025-11-20`，视觉模型预留为 `qwen3.6-plus`。
- DOCX 导入不再因为本地段落/表格存在而跳过内嵌图片 OCR。`python-docx` 本地文本仍作为主路径，符合大小阈值的内嵌图片会进入 OCR；单张图片 OCR 失败时保留本地文本并在 `parse_trace.ocr_failed_count` 与 warnings 中标记，不再把整次导入打成 503。
- `POST /api/admin/content-import/parse` 响应新增 `parse_trace`、`extraction_warnings`、`structure_warnings`、`structure_status`、`structure_error_code` 和 `structure_error_message`。AI 结构化超时、非 JSON、字段无效等情况统一返回本地保守草稿，并给出机器可读错误码，前端据此提示管理员核对字段。
- 后台内容新建页将“人工添加”和“从 Word/PDF 导入”做成模式入口；导入模式显示同步请求阶段进度、OCR 统计和结构化状态。导入成功仍填充同一套内容类型专属字段窗口：最新必读填充更新正文/调整要点，核心基础话术填充基础字段，标准化话术填充场景/推荐话术/禁用话术/注意事项。
- 最新必读详情页正文使用 `white-space: pre-wrap` 保留换行格式，避免发布后的导入正文被压成一段。
- 候选题生成批次和实际 DashScope 调用改用 `DASHSCOPE_QUIZ_MODEL` 与 `DASHSCOPE_QUIZ_TIMEOUT_SECONDS`，避免复用高延迟视觉模型和短默认超时导致“生成后选题”系统性失败。
- 本轮验证：后端 `\.venv\Scripts\python.exe -m pytest backend/tests/test_dashscope_http_phase11.py backend/tests/test_content_import_phase12.py backend/tests/test_quiz_phase2_phase3.py backend/tests/test_quiz_phase5.py -q`、`\.venv\Scripts\python.exe -m pytest backend/tests/test_integrations_phase6.py backend/tests/test_rag_phase6.py backend/tests/test_rag_index_phase6.py -q` 通过；前端 `corepack.cmd pnpm exec vitest run tests/admin-content-phase9.test.ts` 和 `corepack.cmd pnpm build` 通过。

## 2026-07-01 Word/PDF 导入后续修复

- 内容导入拆解候选响应补充 `validation_status`、`is_saveable`、`missing_fields` 和 `quality_warnings`，后端会按内容类型字段契约标记能否直接保存。标准化话术候选必须具备标题、分类、摘要、正文、场景和推荐说法；最新必读和核心基础话术默认不自动拆解。
- 结构化提示词显式声明三类内容的必填字段和禁止模型推断的字段；标准化话术拆解要求章节标题归属后续内容。后端兜底拆分也会修正“块尾残留下一节标题”的边界问题，并给出人工核对警告。
- 后台导入页的拆解候选区新增状态展示和详情编辑。管理员可以查看候选完整正文、缺失字段和质量警告，补齐字段后更新候选；保存选中候选时只创建合格草稿，未合格候选会留在页面并明确列出缺失字段。
- 导入进度条改为“缓慢推进 + 结果返回后快速完成”的混合进度：请求未返回前最高推进到 88%，避免 300ms 内跳到高进度造成假完成感；失败时保留失败阶段提示。
- 后台内容列表新增 `DELETE /api/admin/contents/{content_id}` 草稿删除入口，仅允许管理员删除从未发布过的草稿。已发布或有当前版本的内容不能删除，只能下线，避免破坏历史版本和索引来源。
- 后端新增 `GET /api/admin/content-scenes`，仅管理员可访问，从标准化话术草稿和当前版本结构化字段中读取历史 `scene`，去空、去重并限制最多 100 条；内容编辑页和拆解候选详情页的“场景/候选场景”字段使用原生 `select` 复用这些历史场景。
- 拆解候选详情从列表下方内联展示改为页面内模态窗，候选卡片使用固定网格和可换行标题，避免长标题、勾选框和“缺少字段”状态挤压错位；管理员点击“查看并编辑”会直接看到完整正文、缺失字段和可编辑字段。
- 后台内容列表发布流程从浏览器原生 `confirm + prompt` 改为页面内发布弹窗，弹窗展示标题、类型、可见范围、权限级别和发布影响范围，并要求选择更新级别、填写可选变更摘要；取消不触发 API，确认发布仍调用既有 `POST /api/admin/contents/{content_id}/publish`。
- 拆解候选卡片的勾选框使用独立紧凑样式，避免继承后台表单全局输入框 `width: 100%` 后把候选标题挤成竖排。候选标题来源是结构化响应的 `split_suggestions[].title`，不是摘要或正文。
- 拆解候选详情中的“候选分类”使用原生 `select`，复用内容分类建议集合；单条草稿仍填入下方主表单，主表单“分类”和标准化话术“场景”也使用原生 `select`，不再使用浏览器兼容性较弱的 `input + datalist`。
- 拆解候选卡片内也直接展示“候选分类”和标准化话术的“候选场景”字段，均使用原生 `select`。管理员在候选卡片里修改分类或场景后，会立即更新该候选的结构化 payload 并重新计算缺失字段、可保存状态和保存草稿 payload；导入或 AI 结构化产生的当前值会临时加入选项集合，避免切换为 `select` 后丢失已填值。
- 当前分类/场景建议集合仍属于 MVP 级实现：后端从最近更新的 `contents` 记录中限量读取、去重后返回，不新增权威字典表；大规模生产场景应升级为独立内容分类/场景字典表或物化字典，并按写入侧维护、读侧索引/缓存查询。
- 员工端话术详情页对基础话术正文和标准化话术的推荐说法、禁用说法、注意事项使用 `white-space: pre-wrap`，与最新必读详情页一致保留 Word/PDF 导入正文的段落换行；发布快照仍按纯文本存储，复制文本不改变。
- 本轮验证：后端 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_content_import_phase12.py backend\tests\test_admin_content_phase4.py -q` 通过；前端 `corepack.cmd pnpm exec vitest run tests/admin-content-phase9.test.ts` 为 `18 passed`；前端 `corepack.cmd pnpm build` 通过。
- 本轮增量验证：后端 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_admin_content_phase4.py -q` 为 `14 passed`；前端 `corepack.cmd pnpm exec vitest run tests/admin-content-phase9.test.ts` 为 `20 passed`；前端 `corepack.cmd pnpm build` 通过；内置浏览器在 `http://127.0.0.1:5173/admin/contents` 验证发布按钮打开页面内弹窗且无原生 JS 弹窗，取消后关闭；在 `/admin/contents/new` 验证标准化话术“场景”字段绑定 `content-scene-options` 并读取到历史场景选项。
- 本轮候选卡片修复验证：前端 `corepack.cmd pnpm exec vitest run tests/admin-content-phase9.test.ts` 为 `20 passed`；前端 `corepack.cmd pnpm build` 通过；内置浏览器当前页无拆解候选 DOM，已确认主表单“分类/场景”仍绑定对应 datalist，拆解候选弹窗由组件测试覆盖候选分类/候选场景历史选项和紧凑复选框结构。
