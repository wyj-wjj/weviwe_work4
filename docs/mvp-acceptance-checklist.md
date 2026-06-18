# MVP 验收清单

本清单把 `memory-bank/design-document.md` 第 13 节的 14 条验收标准映射到当前自动化测试和真实环境手测。自动化端到端环境使用 SQLite 与确定性假 DashScope/Milvus 客户端，只验证应用行为；真实 MySQL、Milvus 和 DashScope 链路必须按 `docs/frontend-testing-manual.md` 另行执行。

| 编号 | 验收标准 | 验证证据 | 当前状态 |
| --- | --- | --- | --- |
| 1 | 管理员可以登录后台 | `frontend/e2e/mvp-smoke.spec.ts` 管理员登录与发布用例；`backend/tests/test_e2e_fixture_phase10.py` 三类账号登录契约 | 自动化通过 |
| 2 | 管理员可以创建通用级和全量级内容草稿 | `backend/tests/test_admin_content_phase4.py`；`frontend/tests/admin-content-phase9.test.ts` | 自动化通过 |
| 3 | 管理员可以发布内容并生成版本 | `frontend/e2e/mvp-smoke.spec.ts` 管理员创建、发布并由员工观察用例；`backend/tests/test_admin_content_phase4.py` | 自动化通过 |
| 4 | 已发布内容能在前台按权限展示 | Playwright 通用用户、完整权限用户可见性用例 | 自动化通过 |
| 5 | 已发布内容能同步进入 Milvus 检索范围 | `backend/tests/test_rag_index_phase6.py`；阶段 10 夹具测试确认 6 条 active `vector_index_records` | 自动化通过；真实 Milvus 需手测 |
| 6 | 通用权限账号不能查看或检索全量级内容 | Playwright 列表、直接详情、AI 来源、测验四层隔离用例 | 自动化通过 |
| 7 | 完整权限账号可以查看和检索通用级与全量级内容 | Playwright 完整权限列表、测验和 AI 来源用例 | 自动化通过 |
| 8 | AI 问答能基于命中内容生成回答 | `backend/tests/test_rag_phase6.py` 严格上下文测试；Playwright AI 命中用例 | 自动化通过；真实 DashScope 需手测 |
| 9 | AI 问答结果展示来源和更新时间 | `frontend/tests/employee-quiz-ai-phase8.test.ts`；Playwright AI 来源页面 | 自动化通过 |
| 10 | 未命中问题返回固定提示并写入后台列表 | Playwright AI 未命中与后台列表联动用例 | 自动化通过 |
| 11 | 巩固测试提交后只在当前页面展示对错和解析 | Playwright 测验即时解析用例 | 自动化通过 |
| 12 | 巩固测试不写入答题记录，不保存分数 | `backend/tests/test_migrations_phase2.py`；Playwright 刷新后无历史用例 | 自动化通过 |
| 13 | 历史版本可在后台查看，但不参与当前检索 | `backend/tests/test_admin_content_phase4.py`；`frontend/tests/admin-content-phase9.test.ts` | 自动化通过 |
| 14 | 本地环境完整跑通前端、后端、MySQL、Milvus 和阿里云模型调用 | `docs/frontend-testing-manual.md` 真实全链路操作与核验步骤 | 待真实环境手测记录 |

## 阶段 10 自动化命令

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest

cd E:\WeView\work4\frontend
corepack.cmd pnpm test:unit
corepack.cmd pnpm build
corepack.cmd pnpm test:e2e
```

阶段 10 基线：

- 后端：`61 passed`。
- 前端单元/组件：`43 passed`。
- Playwright：`5 passed`。
- 前端生产构建：成功。
