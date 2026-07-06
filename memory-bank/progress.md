# 开发进度记录

## 2026-06-17：阶段 0、阶段 1、阶段 2、阶段 3

### 已完成范围
- 阶段 0：补充 `docs/phase-0-guardrails.md`，记录不可妥协约束、工作区保护边界、里程碑和测试策略。
- 阶段 1：创建 FastAPI 后端骨架、Vue/Vite 前端骨架、本地开发文档、`.env.example` 安全占位。
- 阶段 2：建立 SQLAlchemy 同步数据库层、Alembic 迁移目录、MVP 数据模型和初始迁移。
- 阶段 3：实现 Argon2 密码哈希、JWT access token、登录 API、当前用户依赖、管理员依赖和内容权限过滤辅助函数。

### 关键实现
- 后端默认面向 MySQL URL；自动化测试使用 SQLite 临时库验证模型、迁移和 API 行为。
- `users` 表覆盖账号、密码哈希、账号类型、内容权限、启用状态和时间戳，并约束用户名唯一。
- 内容相关表包括 `contents`、`content_versions`、`content_chunks`、`vector_index_records`。
- 测验和未命中表包括 `quiz_questions`、`missed_questions`。
- MVP 暂不创建对话持久化表，也不创建测验答题记录、分数或排行类表。
- 登录接口为 `POST /api/auth/login`，当前用户接口为 `GET /api/auth/me`，管理员探针为 `GET /api/admin/ping`。
- 测试中编造了本地用户、内容、版本、chunk、测验题和未命中问题数据，不依赖真实业务数据。

### 验证记录
- 后端：`..\.venv\Scripts\python.exe -m pytest`，结果 `27 passed`。
- 前端：保留阶段 1 的 Vitest 和 build 验证入口；阶段 2/3 未改前端业务逻辑。

## 2026-06-17：阶段 4、阶段 5

### 已完成范围
- 阶段 4：实现管理员内容草稿创建、类型字段校验、草稿编辑、内容列表筛选分页、详情、发布、再发布、历史版本和下线。
- 阶段 4：发布时从草稿字段生成不可变 `content_versions` 快照，并创建当前版本对应的 `content_chunks`；旧 chunk 和下线内容会被排除在 AI 候选 chunk 外。
- 阶段 4：新增 `0002_add_content_draft_fields` 迁移，为 `contents` 增加草稿摘要、草稿正文和草稿结构化载荷。
- 阶段 5：实现员工端最新必读列表/详情、标准话术列表/详情，并在后端按账号权限过滤 `general` 与 `full` 内容。
- 阶段 5：实现后台测验题创建、列表、编辑、启用和禁用；员工端测验抽取 5 到 10 道当前用户可见的启用题。
- 阶段 5：实现员工测验提交即时返回对错、正确答案、解析和关联内容入口；不持久化答题记录、分数或排行。

### 关键实现
- 管理员内容 API 位于 `backend/app/api/routes/content.py`，业务规则集中在 `backend/app/services/content_service.py`。
- 测验 API 位于 `backend/app/api/routes/quiz.py`，业务规则集中在 `backend/app/services/quiz_service.py`。
- `ContentCreate` 对不同内容类型做输入校验：标准化话术必须有 `structured_payload.scene`，最新必读必须有 `update_body` 和 `adjustment_points`。
- 员工端内容查询只返回 `published` 且当前用户可见的当前版本；草稿、历史版本和下线内容不出现在员工接口。
- 测验提交也按当前用户权限二次校验，不允许通用用户提交全量级题目 ID 来绕过列表过滤。
- Milvus 在阶段 4/5 仍未写入；当前发布流程只生成 MySQL 权威数据和可供后续索引阶段消费的 active chunk。
- 本地 MySQL 已用 Alembic 从空库升级到 `head`，并写入 `phase45_*` 烟测账号、最新必读、全量标准话术和通用测验题测试数据。

### 验证记录
- 后端：`..\.venv\Scripts\python.exe -m pytest`，结果 `39 passed`。
- 前端单测：`corepack.cmd pnpm test:unit`，结果 `5 passed`。
- 前端构建：`corepack.cmd pnpm build`，结果成功生成 `dist/`。
- MySQL 烟测：创建/复用 `weview_mvp`，执行 Alembic `upgrade head`，表数量为 8（含 `alembic_version`）；通用用户可见 1 条最新必读、0 条全量标准话术，完整权限用户可见 1 条全量标准话术，通用用户可见 5 道测验题。

### 给后续开发者
- 后续 AI/RAG 阶段应从 `content_chunks` 读取 active chunk 做索引；回答前仍必须回查 MySQL 的当前版本正文。
- 后续若接入 Milvus，`vector_index_records` 只记录索引状态和 Milvus 主键，不得成为正文权威来源。
- 后续前端阶段可以直接对接已存在的内容和测验 API，先复用当前字段，不要在前端绕过后端权限判断。
- 不要把 `.env`、MySQL root 密码、DashScope API Key 或其他真实密钥写入仓库、文档或测试夹具。

## 2026-06-17：阶段 6

### 已完成范围
- 实现核心基础话术、标准化话术和最新必读的切片生成规则，并使用 SHA-256 生成稳定内容哈希。
- 新增 DashScope 集成边界和假客户端，自动化测试只使用假聊天/embedding 响应，不调用真实 DashScope。
- 新增 Milvus 集成边界和假客户端，覆盖 collection schema、向量写入、元数据过滤检索和向量失效行为。
- 新增 `0003_add_content_index_status` 迁移，为 `contents` 增加 `index_status`，持久化 `not_synced`、`synced`、`failed`。
- 发布内容后会生成当前版本 active chunk，并通过索引同步服务调用 embedding、写入 Milvus 抽象、创建 `vector_index_records`。
- 索引失败不会回滚已发布内容；员工端仍可查看内容，后台通过 `index_status=failed` 呈现并支持重试索引。
- 实现员工 RAG 问答 API：问题 embedding、Milvus 候选召回、相似度阈值、MySQL 回查、严格上下文回答和来源返回。
- 实现未命中问题记录、后台列表和标记已处理接口；非管理员不能访问未命中问题管理。

### 关键实现
- `backend/app/integrations/dashscope.py` 封装聊天和 embedding 输出形状、假客户端、真实模式 API Key 检查和供应商错误标准化。
- `backend/app/integrations/milvus.py` 封装 collection 初始化、向量 upsert、检索和失效；当前自动化测试使用内存假客户端。
- `backend/app/services/rag_index_service.py` 负责切片、hash、发布版本 chunk 替换和索引同步。
- `backend/app/services/rag_answer_service.py` 负责 RAG 问答编排；即使 Milvus 返回混合权限结果，也会在 MySQL 回查阶段再次过滤。
- `backend/app/services/missed_question_service.py` 负责未命中问题快照记录、分页列表和标记已处理。
- `backend/app/api/routes/rag.py` 暴露 `POST /api/app/rag/ask`；`backend/app/api/routes/missed_question.py` 暴露后台未命中管理接口。
- `backend/app/api/routes/content.py` 的发布接口现在会触发索引同步，新增 `POST /api/admin/contents/{content_id}/retry-index`。
- `.env.example` 增加 `MILVUS_COLLECTION_NAME`、`RAG_SIMILARITY_THRESHOLD` 和 `RAG_TOP_K` 安全占位。

### 验证记录
- 后端：`..\.venv\Scripts\python.exe -m pytest`，结果 `53 passed`。
- 前端单测：`corepack.cmd pnpm test:unit`，结果 `5 passed`。
- 前端构建：`corepack.cmd pnpm build`，结果成功生成 `dist/`。
- MySQL 烟测：创建/复用 `weview_mvp`，执行 Alembic `upgrade head` 到 `0003_add_content_index_status`；发布并索引一条通用内容后 `index_status=synced`，RAG 命中返回成功，低分未命中返回固定提示并写入后台未命中列表。

### 给后续开发者
- `RealMilvusClient` 已接入 PyMilvus 并通过本地真实 Milvus 写入/检索烟测；自动化测试仍默认用假 Milvus，避免测试依赖外部服务。
- 当前 `DashScopeHttpClient` 仍是边界占位；后续接真实 DashScope 时不要让测试默认调用外网。
- RAG 回答的来源列表只来自进入聊天上下文的 MySQL 回查结果，不能直接信任 Milvus 返回的标题或正文。
- `vector_index_records` 是索引审计和 Milvus 主键记录，不是正文来源；正文仍以 `content_versions` 和 `content_chunks` 为准。
- 后续前端 AI 问答页面可以直接对接 `POST /api/app/rag/ask`，无命中时显示返回的固定 `answer`。

## 2026-06-17：真实 Milvus 写入验证

### 已完成范围
- 安装 `pymilvus` 到后端 `.venv`，并将 `pymilvus>=2.5,<3` 写入 `backend/pyproject.toml`。
- 将 `backend/app/integrations/milvus.py` 的真实模式接到 PyMilvus `MilvusClient`。
- `RealMilvusClient` 支持 collection 创建、显式元数据字段、COSINE 向量索引、upsert 后 flush/load、带权限过滤检索和按内容/版本删除旧向量。

### 验证记录
- 集成边界测试：`..\.venv\Scripts\python.exe -m pytest tests\test_integrations_phase6.py -q`，结果 `5 passed`。
- 后端全量测试：`..\.venv\Scripts\python.exe -m pytest`，结果 `54 passed`。
- 真实 Milvus：连接 `localhost:19530` 成功，创建/复用 `weview_content_chunks`，通过阶段 6 索引同步流程写入 `content-4-version-4-chunk-4`。
- 真实 Milvus 检索：写入后立即用同一向量和 `general` 权限过滤搜索，结果 `search_hit_count=1`、`matching_hit_count=1`。

## 2026-06-17：阶段 7

### 已完成范围
- 实现前端 Pinia 认证状态仓库，保存 token、用户身份、账号类型、内容权限级别，并将会话状态持久化到 `sessionStorage`。
- 实现前端路由守卫：未登录访问 `/app` 重定向到 `/login`，非管理员访问 `/admin` 重定向到员工端，管理员可进入后台。
- 扩展 Axios API client，支持请求注入 Bearer token，并在 401 认证错误时触发清理登录态和跳转登录页。
- 实现登录页表单、必填校验、后端登录 API 调用、成功后按账号类型跳转、失败时统一展示通用错误。
- 实现员工端共享布局，包含 AI 问答入口、最新必读、标准话术、巩固测试三个核心入口，以及用户身份和退出登录。
- 实现后台共享布局，包含内容管理、测验题管理、账号管理和未命中问题导航；非管理员不渲染后台导航。
- 新增全局状态组件，覆盖空状态、加载状态、权限错误、服务错误和 AI 不可用文案。
- 新增复制按钮组件，支持复制成功反馈和失败可恢复提示。

### 关键实现
- `frontend/src/stores/auth.ts` 是前端认证单一状态来源；后续页面应通过该 store 判断登录态和账号类型，不要各页面自行解析 token。
- `frontend/src/router/index.ts` 现在承载认证和管理员守卫，并预留员工端、后台端后续页面路径，阶段 8/9 可替换占位组件。
- `frontend/src/api/client.ts` 提供 `configureApiAuth`，应用启动后由 `main.ts` 注入当前 token 和 401 处理。
- `frontend/src/api/auth.ts` 封装登录 API，响应字段与后端 `LoginResponse` 保持一致。
- `frontend/src/components/EmployeeLayout.vue` 和 `frontend/src/components/AdminLayout.vue` 是阶段 8/9 页面继续复用的区域布局。
- `frontend/src/components/AppState.vue` 与 `frontend/src/components/CopyButton.vue` 是后续内容、RAG 和测验页面的共享 UI 基础件。

### 验证记录
- 前端单测：`corepack.cmd pnpm test:unit`，结果 `23 passed`。
- 前端构建：`corepack.cmd pnpm build`，结果成功生成 `dist/`。
- 后端回归：`..\.venv\Scripts\python.exe -m pytest`，结果 `54 passed`。
- 浏览器烟测：Vite 已在 `http://127.0.0.1:5173` 启动；浏览器打开 `/login` 后可见标题、用户名、密码和登录按钮，页面无横向溢出。

### 给后续开发者
- 阶段 8 员工页面应复用现有 `/app/must-reads`、`/app/scripts`、`/app/quiz` 路由路径，并把当前占位组件替换成具体页面。
- 阶段 9 后台页面应复用现有 `/admin/contents`、`/admin/quiz-questions`、`/admin/users`、`/admin/missed-questions` 路由路径，并继续依赖后台守卫。
- API 模块新增时应复用 `apiClient`，不要绕过全局 token 注入和 401 清登录态行为。
- 登录失败继续使用通用提示，不要在前端区分未知账号、密码错误或禁用账号。

## 2026-06-17：阶段 8

### 已完成范围
- 实现员工首页 AI 提问入口：空问题在前端拦截，非空问题跳转到 `/app/ask?question=...`，并保留最新必读、标准话术、巩固测试三个核心入口。
- 实现员工端最新必读列表与详情页，展示发布时间、生效时间、权限级别、更新正文和调整要点，并在 403 时清空旧内容、展示无权查看提示。
- 实现员工端话术列表与详情页，支持核心基础话术和标准化话术分区、分类过滤、详情字段展示和复制推荐说法/完整条目。
- 实现员工端巩固测试页，渲染 5 到 10 道题、支持单题选择、提交答案、展示正确答案/解析/关联话术入口，不引入分数、排行或答题历史。
- 实现 AI 问答结果页，展示命中回答、来源链接、来源更新时间和复制按钮；未命中显示固定文案；供应商或 RAG 不可用时展示 AI 不可用状态。
- 新增员工端 API 模块 `content.ts`、`quiz.ts`、`rag.ts`，统一复用 `apiClient` 的 token 注入和 401 处理。
- 新增 `frontend/src/utils/format.ts`，集中处理时间、权限标签、内容类型标签和来源详情链接。
- 修正 Vite 本地开发代理：前端默认同源 `/api`，`VITE_API_PROXY_TARGET` 转发到本地 FastAPI，避免浏览器跨域和 API 路径错位。
- 新增阶段 8 前端手测手册 `docs/frontend-testing-manual.md`，并新增本地 seed 辅助脚本 `docs/seed-phase8-manual-data.py`。

### 关键实现
- `frontend/src/router/index.ts` 已将阶段 7 的员工端占位路由替换为真实页面：`/app/must-reads`、`/app/must-reads/:contentId`、`/app/scripts`、`/app/scripts/:contentId`、`/app/quiz`、`/app/ask`。
- `EmployeeLayout` 现在承担员工端全局 AI 提问表单，子页面只负责各自业务内容。
- 员工端内容页面只消费后端已过滤的员工 API；前端不尝试自行扩大权限，也不缓存或展示权限错误前的旧详情。
- `frontend/.env` 或 `.env.local` 推荐使用 `VITE_API_BASE_URL=/api`，开发期由 Vite proxy 转发到后端。
- `docs/seed-phase8-manual-data.py` 只准备本地手测账号、内容和题目，不写入真实密钥，也不伪造真实 Milvus 索引完成状态。

### 验证记录
- 前端单测：`corepack.cmd pnpm test:unit`，结果 `36 passed`。
- 前端构建：`corepack.cmd pnpm build`，结果成功生成 `dist/`。
- 后端回归：`..\.venv\Scripts\python.exe -m pytest`，结果 `54 passed`，仅保留测试 JWT 密钥长度 warning。
- 浏览器烟测：独立启动当前后端 `http://127.0.0.1:8001` 和前端 `http://127.0.0.1:5174`，完成登录、员工首页、最新必读、巩固测试和 AI 未命中状态验证。

### 给后续开发者
- 阶段 9 后台页面可以直接复用当前 API client、AppState、CopyButton 和 Vite proxy 配置。
- 员工端 AI 成功命中依赖真实 DashScope、Milvus 和索引同步；阶段 8 手测脚本只负责业务数据，不负责跨进程 fake Milvus 索引。
- 若继续补充前端页面，请把新 API 封装放在 `frontend/src/api/`，不要在 Vue 页面里直接拼 axios 实例或绕过统一错误处理。

## 2026-06-18：阶段 9

### 已完成范围
- 实现后台内容列表、筛选、分页、状态标签和按状态显示的编辑、发布、下线、历史版本、索引重试入口。
- 实现后台内容编辑器，覆盖通用字段、标准化话术专属字段、最新必读专属字段，以及新建/编辑草稿流程。
- 实现发布确认、发布结果、下线确认、历史版本和索引重试界面。
- 实现后台测验题列表与编辑器，支持新建、编辑、启用和禁用。
- 实现后台账号列表、新建、编辑、密码重置和禁用；员工账号管理入口只维护 `general_user` 和 `full_user`，管理员账号只读。
- 实现后台未命中问题列表、状态筛选和标记已处理；未引入统计看板、图表或排行。
- 新增最小后端账号管理 API，并补充测验题和历史版本的后台展示字段。

### 关键实现
- 后台页面统一复用 `AdminLayout`、`AppState`、`apiClient` 和全局后台样式，不创建独立 Axios 实例。
- 后台内容、测验、账号和未命中 API 分别封装在 `frontend/src/api/admin-content.ts`、`admin-quiz.ts`、`admin-users.ts`、`admin-missed-questions.ts`。
- 后台真实页面位于 `frontend/src/pages/admin/`；路由增加内容新建、编辑和历史版本子路由。
- 后端新增 `backend/app/api/routes/user.py` 和 `backend/app/services/user_service.py`，提供员工账号的创建、分页列表、编辑、密码重置和禁用。
- 后端账号管理不返回密码或密码哈希；密码重置只返回成功标志，前端一次性提示管理员安全通知用户。
- 后端拒绝通过员工账号管理入口创建、提升、编辑、重置或禁用管理员账号。
- 内容历史接口新增 `created_by_name`。当前数据模型没有单独保存历史权限快照，因此历史页权限暂来自内容当前权限级别。
- 索引状态界面兼容 `not_synced`、`syncing`、`synced`、`failed`；当前后端持久化枚举仍为前三者中的 `not_synced`、`synced`、`failed`。

### 验证记录
- 后端：`..\.venv\Scripts\python.exe -m pytest`，结果 `59 passed`。
- 前端单测：`corepack.cmd pnpm test:unit`，结果 `43 passed`。
- 前端构建：`corepack.cmd pnpm build`，结果成功生成 `dist/`。
- 差异检查：`git diff --check` 无空白错误，仅提示既有文件换行格式将在 Git 后续处理时规范化。
- 浏览器烟测补充完成：使用内置 Browser 打开 `http://127.0.0.1:5173`，通过临时 SQLite 后端完成管理员登录、后台首页、内容筛选、内容编辑器动态字段、历史版本、测验题、账号和未命中页面验证；浏览器控制台无 warning/error。
- 响应式检查：桌面后台布局正常；599px 窄屏业务页无全局横向溢出，表格使用内部横向滚动。后台首页窄屏下深色导航区域偏高，属于后续可优化的视觉问题。
- 烟测结束后已停止临时 FastAPI 进程并删除 `backend/phase9-browser-smoke.db`，未改动真实 MySQL 数据。

### 给后续开发者
- 阶段 10 Playwright 冒烟测试应优先覆盖管理员创建/发布内容、账号禁用后登录失败、测验题启停和未命中问题处理。
- 若要准确展示历史版本“发布当时的权限级别”，需要新增迁移把权限快照写入 `content_versions`。
- 若引入真实“同步中”状态，需要先扩展后端 `IndexStatus` 枚举和数据库约束，再让索引服务在同步前后更新状态。
- 管理员账号初始化和自身密码维护继续走运维流程，不要复用员工账号管理入口。
- 后台新页面继续通过 `frontend/src/api/` 封装请求，并保留后端管理员依赖作为最终权限边界。

## 2026-06-18：阶段 10

### 已完成范围
- 新增确定性的端到端后端夹具，包含管理员、完整权限员工、通用权限员工，六条跨通用/全量权限的最新必读、基础话术和标准化话术，以及五道通用题和一道全量题。
- 新增阶段 10 专用 FastAPI 启动器。它只使用 `backend/tmp/phase10-e2e.db` 和进程内假外部客户端，不读取或改动真实 MySQL、Milvus 和 DashScope 数据。
- 假 Milvus 现在按余弦相似度计算默认检索分数，使正向向量稳定命中、反向向量稳定低于阈值；显式 `search_results` 测试路径保持不变。
- 新增 Playwright Chromium 配置和五条串行冒烟测试，覆盖管理员发布、通用用户四层权限隔离、完整权限可见与检索、AI 未命中回写后台、测验不持久化。
- Vitest 发现范围限定到 `frontend/tests/**/*.test.ts`，避免把 Playwright `e2e/*.spec.ts` 当作 jsdom 单测加载。
- 新增 `docs/mvp-acceptance-checklist.md`，把产品设计文档中的 14 条验收标准映射到自动化测试或真实环境手测。

### 关键实现
- `backend/app/e2e_fixture.py`：定义阶段 10 固定账号、内容、测验和命中/未命中 AI 假客户端；所有发布夹具都会经过既有内容发布、chunk、embedding、Milvus 抽象和索引记录流程。
- `backend/e2e_server.py`：重建专用 SQLite 表、加载夹具、把同一组假 DashScope/Milvus 实例注入发布和问答请求，然后在 `127.0.0.1:8010` 启动测试服务。
- `backend/tests/test_e2e_fixture_phase10.py`：验证三类账号登录、内容权限、题目权限、RAG 命中/未命中和 6 条索引记录。
- `frontend/playwright.config.ts`：单 worker 启动阶段 10 后端和 `5175` Vite 前端，统一使用 Chromium 执行。
- `frontend/e2e/mvp-smoke.spec.ts`：通过浏览器和真实 HTTP API 操作页面，不 mock Axios 或 Vue 组件。

### 验证记录
- 后端：`..\.venv\Scripts\python.exe -m pytest`，结果 `61 passed`。
- 前端单测：`corepack.cmd pnpm test:unit`，结果 `43 passed`。
- 前端构建：`corepack.cmd pnpm build`，结果成功。
- Playwright：`corepack.cmd pnpm test:e2e`，结果 `5 passed`。
- 内置 Browser 复验：完整权限账号可同时看到通用级和全量级基础/标准话术；AI 命中页展示通用与全量来源和更新时间；控制台无 warning/error。

### 给后续开发者
- 阶段 10 专用账号密码和 SQLite 数据只用于自动化，不可作为手工真实环境数据，也不能用于生产。
- E2E 测试依赖共享的进程内假 Milvus；不要把发布和问答拆到不同测试后端进程，否则向量状态不会共享。
- `frontend/e2e` 与 `frontend/tests` 分属 Playwright 和 Vitest，新增测试时保持目录与命名边界。
- 产品验收第 14 条仍需使用真实 MySQL、真实 Milvus 和真实 DashScope 完成手测并记录。

## 2026-06-18：阶段 11 与真实全链路手册

### 已完成范围
- 实现真实 `DashScopeHttpClient`，通过 OpenAI-compatible `/embeddings` 调用 `text-embedding-v4`，通过 `/chat/completions` 调用 `qwen-plus`。
- 真实聊天提示词只允许使用已经过权限和有效状态校验的来源，不允许补充来源中没有的业务结论。
- 将 httpx 移入后端运行依赖，并用 `httpx.MockTransport` 覆盖请求体、鉴权头、响应解析、401/403、超时、HTTP 错误和异常响应。
- Alembic 默认占位 URL 现在会从仓库根目录 `.env` 读取 `DATABASE_URL`；测试显式 SQLite URL 保持优先。
- 新增初始管理员 CLI，支持创建或更新管理员、Argon2 哈希密码和重新启用。
- 重写本地开发说明和完整前端真实链路测试手册，新增宝塔/ECS 部署说明。
- 完整手册要求除首个管理员外，员工账号、内容、测验、发布、索引和未命中问题全部从前端经 FastAPI 写入真实 MySQL/Milvus。

### 关键实现
- `backend/app/integrations/dashscope.py`：真实 HTTP 调用、严格上下文消息、标准化输出和错误映射。
- `backend/alembic/env.py`：仅当 `alembic.ini` 仍为占位 URL 时加载根目录 `.env`。
- `backend/app/cli/create_admin.py`：首个管理员运维入口。
- `docs/local-development.md`：完整本地安装、配置、迁移、启动和测试命令。
- `docs/deployment-bt-ecs.md`：静态前端、Python 后端、Nginx/宝塔、MySQL、Milvus、DashScope 部署边界。
- `docs/frontend-testing-manual.md`：从管理员前端创建真实账号/内容/测验、发布索引、员工权限、AI 命中/未命中和落库核验。

### 验证记录
- DashScope 单元契约：embedding/chat 和错误映射测试通过。
- 真实 DashScope：`text-embedding-v4` 返回 1024 维向量；`qwen-plus` 返回非空回答和 prompt/completion/total token usage。
- 真实 Milvus：将 1024 维真实 embedding 写入 `weview_codex_phase11_smoke_v4` 后检索命中 1 条，随后删除测试实体。
- 文档契约：本地开发、宝塔/ECS、真实前端全链路三组检查通过。
- 后端全量：`..\.venv\Scripts\python.exe -m pytest`，结果 `71 passed`。
- 前端单测：`corepack.cmd pnpm test:unit`，结果 `43 passed`。
- 前端构建：`corepack.cmd pnpm build`，结果成功。
- Playwright：`corepack.cmd pnpm test:e2e`，结果 `5 passed`。
- 真实浏览器全链路：管理员前端创建 `codex_real_general` 和“Codex真实链路风险提示话术”，发布后显示 `v1 / synced`；MySQL 记录 current version 和 1024 维索引审计，Milvus 检索命中同一内容，通用员工获得 `qwen-plus` 回答和正确来源。
- 真实未命中：无关问题返回固定提示，并进入管理员未命中问题列表，账号和权限快照正确。
- 安全检查：误写入 `.env.example` 的本地数据库凭据已恢复为占位值，未进入暂存区或提交。

### 给后续开发者
- 后续可按 `docs/frontend-testing-manual.md` 使用自定义测试账号重复执行，不要复用或传播本次临时账号密码。
- 不要为绕过本地凭据问题把真实手测改回 SQLite 或假客户端。
- 不要复用旧 3 维 Milvus collection；真实 `text-embedding-v4` 使用独立 1024 维 collection。
- 真实服务检查结果只能记录模型名、维度、collection 和行为，不记录密码、API Key、JWT 或完整 token。

## 2026-07-06 增量修复
- **RAG 流式输出（SSE）全面替换**
  - **问题**：旧版 RAG 需要等大模型完全生成后才返回，导致首字延迟（TTFT）过长，用户体验卡顿。
  - **解决**：废弃了前端等待全量返回的模式，重构为端到端流式架构。
    - 后端：在 `dashscope.py` 实现了基于 `httpx.Client.stream` 的真正流式请求；在 `rag_answer_service.py` 实现了自定义的 SSE 格式（`sources`, `content`, `done`, `error`）；在 FastAPI 路由中使用 `StreamingResponse` 返回生成器。
    - 前端：废弃 axios，采用原生 `fetch` 与 `ReadableStream` 编写轻量级 SSE 解析器；在员工端问答页面实现了逐字渲染的打字机光标特效。
  - **状态**：✅ 已完成，全栈流式链路跑通，前后端测试套件（`test_rag_phase6.py` 和 `employee-quiz-ai-phase8.test.ts`）全部通过。

- **RAG 极速模式（fast_extractive）回答失焦修复**
  - **问题**：AI 问答检索命中文本后，返回的却是文章开头或摘要内容。
  - **原因**：合并同源上下文时，包含了前序块并优先排列；且精简截断逻辑固定取前 6 行且未过滤“摘要：”前缀。
  - **解决**：在 `rag_answer_service.py` 中精准收集实际命中的核心块 (`hit_texts`) 并在展示阶段优先基于此核心块生成摘要，同时补充过滤“摘要：”元数据前缀。
  - **状态**：✅ 已完成，后端测试通过（`test_rag_phase6.py`）。
