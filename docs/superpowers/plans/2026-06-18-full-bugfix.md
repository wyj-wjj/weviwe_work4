# Full Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复企业话术系统的 AI 串答、召回、复制、测验、发布幂等、外部服务重试和测试数据污染问题，并完成自动化及真实浏览器回归。

**Architecture:** 保持 Vue SPA + FastAPI 单体 + MySQL 权威数据源 + Milvus 索引边界。前端用请求取消和序号隔离异步状态；后端通过稳定索引文本、严格 MySQL 回查、测验关联契约、草稿修订号和有限 HTTP 重试建立业务不变量。

**Tech Stack:** Vue 3、TypeScript、Axios、Vitest、FastAPI、SQLAlchemy 2、Alembic、httpx、pytest、Playwright。

---

## File Map

### Frontend

- Modify `frontend/src/api/rag.ts`: 接受 `AbortSignal`。
- Modify `frontend/src/pages/app/AiAnswerPage.vue`: 请求取消、序号隔离、卸载清理。
- Modify `frontend/src/components/EmployeeLayout.vue`: 相同问题防重复路由提交。
- Modify `frontend/src/components/CopyButton.vue`: Clipboard API 降级复制。
- Modify `frontend/src/api/quiz.ts`: 增加关联内容类型。
- Modify `frontend/src/pages/app/QuizPage.vue`: 依据内容类型生成安全链接。
- Modify `frontend/src/pages/admin/ContentListPage.vue`: 发布、下线、索引重试 pending 状态。
- Modify `frontend/tests/employee-quiz-ai-phase8.test.ts`: AI 竞态和测验链接回归。
- Modify `frontend/tests/shared-ui.test.ts`: 复制三态回归。
- Modify `frontend/tests/admin-content-phase9.test.ts`: 发布 pending 和取消确认。

### Backend

- Create `backend/alembic/versions/0004_add_publish_revision_and_version_permission.py`: 草稿修订和版本权限快照迁移。
- Modify `backend/app/models/content.py`: 新增修订字段和版本权限快照。
- Modify `backend/app/services/content_service.py`: 草稿修订、行锁和同修订发布幂等。
- Modify `backend/app/api/routes/content.py`: 历史版本使用权限快照。
- Modify `backend/app/services/rag_index_service.py`: 构造完整稳定检索文本。
- Modify `backend/app/services/rag_answer_service.py`: 查询扩展、候选合并、相对分数窗口。
- Modify `backend/app/integrations/dashscope.py`: 临时错误有限重试和分类。
- Modify `backend/app/services/quiz_service.py`: 权限抽题和关联内容可见性契约。
- Modify `backend/app/api/routes/quiz.py`: 员工响应和提交结果返回关联类型。
- Modify `backend/app/schemas/quiz.py`: 如需要，补充响应辅助类型。
- Modify `backend/app/e2e_fixture.py`: 可区分权限、召回和链接的确定性夹具。
- Create `backend/app/cli/audit_test_data.py`: 默认 dry-run 的测试数据审计/清理命令。
- Modify `docs/seed-phase8-manual-data.py`: UTF-8、幂等、通用/全量题准备。

### Tests and Documentation

- Modify `backend/tests/test_migrations_phase2.py`: 0004 升降级覆盖。
- Modify `backend/tests/test_admin_content_phase4.py`: 草稿与发布幂等。
- Modify `backend/tests/test_rag_index_phase6.py`: 索引文本字段覆盖。
- Modify `backend/tests/test_rag_phase6.py`: 查询扩展、来源相关性和权限。
- Modify `backend/tests/test_quiz_phase5.py`: 抽题和关联类型。
- Modify `backend/tests/test_dashscope_http_phase11.py`: 重试分类。
- Create `backend/tests/test_test_data_audit.py`: dry-run 和已知数据边界。
- Modify `frontend/e2e/mvp-smoke.spec.ts`: Bug 清单浏览器回归。
- Modify `docs/测试prompt.md`: 循环寿命改由完整员工测试。
- Modify `docs/frontend-testing-manual.md`: 修正敏感密码并说明数据分层。
- Modify `docs/local-development.md`: 审计/清理和重建索引说明。
- Modify `memory-bank/architecture.md`: 记录最终架构与验证基线。

## Task 1: AI 请求竞态隔离

**Files:**

- Modify: `frontend/tests/employee-quiz-ai-phase8.test.ts`
- Modify: `frontend/src/api/rag.ts`
- Modify: `frontend/src/pages/app/AiAnswerPage.vue`
- Modify: `frontend/src/components/EmployeeLayout.vue`

- [ ] **Step 1: Write failing tests for stale success and stale failure**

在 `frontend/tests/employee-quiz-ai-phase8.test.ts` 增加可控 Promise：

```ts
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

test('AI page ignores an older success after a newer question succeeds', async () => {
  const oldRequest = deferred<Awaited<ReturnType<typeof askRag>>>()
  const newRequest = deferred<Awaited<ReturnType<typeof askRag>>>()
  mockedAskRag.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)

  const view = await renderAppPage(AiAnswerPage, '/app/ask?question=旧问题')
  await view.router.push('/app/ask?question=新问题')
  newRequest.resolve({ hit: true, answer: '新回答', sources: [] })
  await waitFor(() => expect(view.getByText('新回答')).toBeInTheDocument())

  oldRequest.resolve({ hit: true, answer: '旧回答', sources: [] })
  await Promise.resolve()
  expect(view.queryByText('旧回答')).not.toBeInTheDocument()
  expect(view.getByText('问题：新问题')).toBeInTheDocument()
})

test('AI page ignores an older error after a newer question succeeds', async () => {
  const oldRequest = deferred<Awaited<ReturnType<typeof askRag>>>()
  const newRequest = deferred<Awaited<ReturnType<typeof askRag>>>()
  mockedAskRag.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)

  const view = await renderAppPage(AiAnswerPage, '/app/ask?question=旧问题')
  await view.router.push('/app/ask?question=新问题')
  newRequest.resolve({ hit: true, answer: '新回答', sources: [] })
  await waitFor(() => expect(view.getByText('新回答')).toBeInTheDocument())

  oldRequest.reject({ status: 503, code: 'ai_unavailable' })
  await Promise.resolve()
  expect(view.queryByText('智能问答暂不可用，请稍后重试')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm vitest run tests/employee-quiz-ai-phase8.test.ts
```

Expected: stale response tests fail because the older Promise overwrites `answer` or `state`.

- [ ] **Step 3: Add cancellation to the API contract**

Change `frontend/src/api/rag.ts`:

```ts
export async function askRag(
  question: string,
  signal?: AbortSignal,
): Promise<RagAnswerResponse> {
  const response = await apiClient.post<RagAnswerResponse>(
    '/app/rag/ask',
    { question },
    { signal },
  )
  return response.data
}
```

- [ ] **Step 4: Implement request sequence and unmount cleanup**

In `frontend/src/pages/app/AiAnswerPage.vue`:

```ts
import { computed, onBeforeUnmount, ref, watch } from 'vue'

let requestSequence = 0
let activeController: AbortController | null = null

watch(
  question,
  async (currentQuestion) => {
    requestSequence += 1
    const sequence = requestSequence
    activeController?.abort()
    activeController = null
    answer.value = null

    const normalizedQuestion = currentQuestion.trim()
    if (!normalizedQuestion) {
      state.value = 'empty'
      return
    }

    const controller = new AbortController()
    activeController = controller
    state.value = 'loading'
    try {
      const result = await askRag(normalizedQuestion, controller.signal)
      if (sequence !== requestSequence || controller.signal.aborted) return
      answer.value = result
      state.value = 'ready'
    } catch (error) {
      if (sequence !== requestSequence || controller.signal.aborted) return
      const apiError = error as { code?: string; status?: number }
      state.value =
        apiError.code === 'ai_unavailable' || apiError.status === 503
          ? 'ai-unavailable'
          : 'service'
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  requestSequence += 1
  activeController?.abort()
})
```

In `EmployeeLayout.vue`, before `router.push`, return when the current route is already `employee-ai-answer` with the same trimmed question.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
corepack.cmd pnpm vitest run tests/employee-quiz-ai-phase8.test.ts
```

Expected: all tests in the file pass.

## Task 2: Clipboard API fallback

**Files:**

- Modify: `frontend/tests/shared-ui.test.ts`
- Modify: `frontend/src/components/CopyButton.vue`

- [ ] **Step 1: Write failing fallback tests**

Add tests that mock `document.execCommand`:

```ts
test('copy button falls back to execCommand when Clipboard API rejects', async () => {
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
  })
  const execCommand = vi.spyOn(document, 'execCommand').mockReturnValue(true)
  const view = render(CopyButton, { props: { text: '推荐说法' } })

  await fireEvent.click(view.getByRole('button', { name: '复制' }))

  await waitFor(() => expect(view.getByText('已复制')).toBeInTheDocument())
  expect(execCommand).toHaveBeenCalledWith('copy')
  expect(document.querySelector('[data-copy-fallback]')).toBeNull()
})

test('copy button reports failure when Clipboard API and fallback both fail', async () => {
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
  })
  vi.spyOn(document, 'execCommand').mockReturnValue(false)
  const view = render(CopyButton, { props: { text: '推荐说法' } })

  await fireEvent.click(view.getByRole('button', { name: '复制' }))

  await waitFor(() => expect(view.getByText('复制失败，请重试')).toBeInTheDocument())
})
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
corepack.cmd pnpm vitest run tests/shared-ui.test.ts
```

Expected: fallback-success test fails with failure feedback.

- [ ] **Step 3: Implement the fallback**

Add a helper in `CopyButton.vue`:

```ts
function fallbackCopy(text: string): boolean {
  const activeElement = document.activeElement instanceof HTMLElement
    ? document.activeElement
    : null
  const selection = window.getSelection()
  const savedRanges = selection
    ? Array.from({ length: selection.rangeCount }, (_, index) => selection.getRangeAt(index).cloneRange())
    : []
  const textarea = document.createElement('textarea')
  textarea.dataset.copyFallback = 'true'
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()

  try {
    return document.execCommand('copy')
  } finally {
    textarea.remove()
    if (selection) {
      selection.removeAllRanges()
      savedRanges.forEach((range) => selection.addRange(range))
    }
    activeElement?.focus()
  }
}

async function copyText() {
  feedback.value = ''
  try {
    if (!navigator.clipboard?.writeText) throw new Error('clipboard unavailable')
    await navigator.clipboard.writeText(props.text)
    feedback.value = '已复制'
  } catch {
    feedback.value = fallbackCopy(props.text) ? '已复制' : '复制失败，请重试'
  }
}
```

- [ ] **Step 4: Run and verify GREEN**

Run:

```powershell
corepack.cmd pnpm vitest run tests/shared-ui.test.ts tests/employee-content-phase8.test.ts
```

Expected: Clipboard API success, fallback success and total failure tests pass.

## Task 3: RAG indexing, query expansion, source consistency

**Files:**

- Modify: `backend/tests/test_rag_index_phase6.py`
- Modify: `backend/tests/test_rag_phase6.py`
- Modify: `backend/app/services/rag_index_service.py`
- Modify: `backend/app/services/rag_answer_service.py`
- Modify: `backend/app/integrations/dashscope.py`

- [ ] **Step 1: Write failing index-text tests**

Extend `test_chunk_generation_rules_keep_metadata_and_business_boundaries`:

```python
assert "标题：Scenario" in standard_chunk.chunk_text
assert "分类：sales" in standard_chunk.chunk_text
assert "摘要：" in standard_chunk.chunk_text
assert "场景：Price objection" in standard_chunk.chunk_text
assert "注意事项：Keep the tone calm." in standard_chunk.chunk_text

base_chunk = next(item for item in chunks if item.content_id == base.id)
assert "正文：Base approved text." in base_chunk.chunk_text
```

Create a base payload with `summary="Return calculation"` and
`structured_payload={"points": ["IRR 12-15%", "回收期 3-5 年"]}`, then assert both facts are in the chunk.

- [ ] **Step 2: Run index tests and verify RED**

Run:

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest -q tests/test_rag_index_phase6.py
```

Expected: assertions for title, summary and points fail.

- [ ] **Step 3: Implement stable field-labelled index text**

Add helpers to `rag_index_service.py`:

```python
def text_field(label: str, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        rendered = "\n".join(str(item).strip() for item in value if str(item).strip())
    else:
        rendered = str(value).strip()
    return f"{label}：{rendered}" if rendered else None


def common_chunk_fields(content: Content, version: ContentVersion) -> list[str]:
    return [
        field
        for field in [
            text_field("标题", version.title),
            text_field("分类", content.category),
            text_field("摘要", version.summary),
        ]
        if field
    ]
```

Build each chunk from common fields plus its type-specific labelled fields. For base scripts include `正文` and `要点`; for standard scripts include all four structured fields; for must-reads include `更新正文` and `调整要点`.

- [ ] **Step 4: Write failing query-expansion and source-window tests**

In `test_rag_phase6.py`:

```python
def test_short_cycle_life_question_uses_expanded_embedding_text(db_session):
    user = make_user(db_session, username="full-cycle", account_type="full_user", content_level="full")
    dashscope = FakeDashScopeClient(chat_answer="6000-8000 次", embedding=[1.0, 0.0, 0.0])
    milvus = FakeMilvusClient(search_results=[])

    answer_question(
        db_session,
        user=user,
        question="电池能用多少次？",
        dashscope_client=dashscope,
        milvus_client=milvus,
    )

    assert dashscope.embedding_requests == ["电池能用多少次？ 电池循环寿命 充放电循环次数"]
```

Add a test with valid scores `0.91`, `0.89`, `0.71` and assert only the first two contexts and sources are returned when the relative score window is `0.12`.

Add a permission test where a general user receives a high-scoring full hit and a lower general hit; assert the full hit never enters chat contexts or response sources.

- [ ] **Step 5: Run RAG tests and verify RED**

Run:

```powershell
..\.venv\Scripts\python.exe -m pytest -q tests/test_rag_phase6.py
```

Expected: query embedding text and source-window assertions fail.

- [ ] **Step 6: Implement deterministic query expansion and context merging**

In `rag_answer_service.py`:

```python
QUERY_EXPANSIONS = (
    (("电池能用多少次", "能循环多少次"), "电池循环寿命 充放电循环次数"),
)
RELATIVE_SCORE_WINDOW = 0.12


def retrieval_question(question: str) -> str:
    normalized = question.strip()
    for phrases, expansion in QUERY_EXPANSIONS:
        if any(phrase in normalized for phrase in phrases):
            return f"{normalized} {expansion}"
    return normalized
```

Embed `retrieval_question(question)`. In `load_authorized_contexts`, sort hits descending, establish the first authorized score, reject scores below `first_score - RELATIVE_SCORE_WINDOW`, and merge repeated `content_id` texts while retaining the highest-scoring source.

- [ ] **Step 7: Strengthen the answer prompt**

Change the system prompt in `dashscope.py` to include:

```python
"先直接回答用户问题，并覆盖来源中与问题直接相关的关键数字、条件和限制。"
"不要机械罗列与问题无关的来源内容。来源不足时明确说明不足。"
```

- [ ] **Step 8: Run focused RAG tests and verify GREEN**

Run:

```powershell
..\.venv\Scripts\python.exe -m pytest -q tests/test_rag_index_phase6.py tests/test_rag_phase6.py
```

Expected: all focused RAG tests pass.

## Task 4: DashScope transient retry

**Files:**

- Modify: `backend/tests/test_dashscope_http_phase11.py`
- Modify: `backend/app/integrations/dashscope.py`

- [ ] **Step 1: Write retry classification tests**

Use `httpx.MockTransport` with counters:

```python
def test_dashscope_retries_timeout_and_then_succeeds(settings):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ReadTimeout("temporary", request=request)
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2]}], "model": "text-embedding-v4"},
        )

    client = DashScopeHttpClient(
        settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )
    assert client.embed_text("hello").vector == [0.1, 0.2]
    assert attempts == 3
```

Add equivalent tests for 429 then success, 503 then success, and assertions that 401 and invalid JSON make exactly one attempt.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
..\.venv\Scripts\python.exe -m pytest -q tests/test_dashscope_http_phase11.py
```

Expected: constructor does not accept `sleep`, or only one request is attempted.

- [ ] **Step 3: Implement bounded retry**

Update `DashScopeHttpClient`:

```python
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

def __init__(self, settings: Settings, *, http_client=None, sleep=time.sleep) -> None:
    self.settings = settings
    self.http_client = http_client
    self.sleep = sleep

def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    for attempt in range(3):
        try:
            response = self._send(path, payload)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if attempt == 2:
                raise ProviderTimeoutError("DashScope request timed out.") from exc
            self.sleep(0.2 * (2**attempt))
            continue

        if response.status_code in {401, 403}:
            raise ProviderAuthenticationError("DashScope authentication failed.")
        if response.status_code in RETRYABLE_STATUS_CODES:
            if attempt == 2:
                raise ProviderResponseError(
                    f"DashScope returned temporary HTTP {response.status_code}."
                )
            self.sleep(0.2 * (2**attempt))
            continue
        if response.status_code >= 400:
            raise ProviderResponseError(f"DashScope returned HTTP {response.status_code}.")
        return self._decode_response(response)
    raise ProviderResponseError("DashScope retry loop exhausted.")
```

Keep headers local to `_send`; do not log Authorization.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
..\.venv\Scripts\python.exe -m pytest -q tests/test_dashscope_http_phase11.py tests/test_integrations_phase6.py
```

Expected: retryable failures recover within three attempts; permanent failures attempt once.

## Task 5: Quiz permissions and related content contract

**Files:**

- Modify: `backend/tests/test_quiz_phase5.py`
- Modify: `backend/app/services/quiz_service.py`
- Modify: `backend/app/api/routes/quiz.py`
- Modify: `frontend/src/api/quiz.ts`
- Modify: `frontend/src/pages/app/QuizPage.vue`
- Modify: `frontend/tests/employee-quiz-ai-phase8.test.ts`

- [ ] **Step 1: Write backend failing tests**

Add a test that creates 12 general and 1 full enabled question, then asserts:

```python
full_items = client.get("/api/app/quiz", headers=full_user_headers).json()["items"]
assert len(full_items) == 10
assert any(item["permission_level"] == "full" for item in full_items)
```

Create published `base_script`, `standard_script`, and `must_read` contents and assert employee quiz responses include the corresponding `related_content_type`.

Create offline and full-only related content and assert a general-user response returns:

```python
assert item["related_content_id"] is None
assert item["related_content_type"] is None
```

- [ ] **Step 2: Run backend tests and verify RED**

Run:

```powershell
..\.venv\Scripts\python.exe -m pytest -q tests/test_quiz_phase5.py
```

Expected: full question is excluded by the first ten IDs and `related_content_type` is missing.

- [ ] **Step 3: Implement deterministic sampling and safe relation projection**

In `quiz_service.py`:

```python
def visible_related_content(question: QuizQuestion, user: User):
    content = question.related_content
    if (
        content is None
        or content.status != "published"
        or content.current_version_id is None
        or content.permission_level not in visible_levels_for(user)
    ):
        return None
    return content


def list_employee_quiz_questions(db: Session, user: User) -> list[QuizQuestion]:
    base = (
        select(QuizQuestion)
        .where(QuizQuestion.status == QuestionStatus.ENABLED.value)
        .where(QuizQuestion.permission_level.in_(visible_levels_for(user)))
        .order_by(QuizQuestion.id.asc())
    )
    items = list(db.scalars(base).all())
    if user.account_type not in {"admin", "full_user"}:
        return items[:10]
    full_items = [item for item in items if item.permission_level == "full"]
    general_items = [item for item in items if item.permission_level == "general"]
    selected = full_items[:1] + general_items
    selected.extend(full_items[1:])
    return selected[:10]
```

Allow `quiz_to_dict` to accept `user` and project safe relation fields. Use the same projection in submit results.

- [ ] **Step 4: Add frontend failing route tests**

Extend the existing quiz submit test with `related_content_type: 'must_read'` and expect:

```ts
expect(getByRole('link', { name: '查看关联话术' }))
  .toHaveAttribute('href', '/app/must-reads/21')
```

Add base and standard cases expecting `/app/scripts/{id}`, plus a null-type case expecting no link.

- [ ] **Step 5: Run frontend test and verify RED**

Run:

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm vitest run tests/employee-quiz-ai-phase8.test.ts
```

Expected: must-read test receives the hard-coded scripts URL.

- [ ] **Step 6: Implement frontend relation type**

Add `related_content_type: 'base_script' | 'standard_script' | 'must_read' | null` to question/result types. In `QuizPage.vue`:

```ts
import { sourceDetailPath } from '../../utils/format'

function relatedPath(result: QuizSubmitResult) {
  if (!result.related_content_id || !result.related_content_type) return null
  return sourceDetailPath(result.related_content_type, result.related_content_id)
}
```

Render `RouterLink` only when `relatedPath(result)` is non-null.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run:

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest -q tests/test_quiz_phase5.py
cd E:\WeView\work4\frontend
corepack.cmd pnpm vitest run tests/employee-quiz-ai-phase8.test.ts
```

Expected: backend permissions and all three related paths pass.

## Task 6: Publish idempotency and version permission snapshot

**Files:**

- Modify: `backend/tests/test_migrations_phase2.py`
- Modify: `backend/tests/test_admin_content_phase4.py`
- Create: `backend/alembic/versions/0004_add_publish_revision_and_version_permission.py`
- Modify: `backend/app/models/content.py`
- Modify: `backend/app/services/content_service.py`
- Modify: `backend/app/api/routes/content.py`
- Modify: `frontend/tests/admin-content-phase9.test.ts`
- Modify: `frontend/src/pages/admin/ContentListPage.vue`

- [ ] **Step 1: Write migration failing assertions**

Update expected columns:

```python
assert {"draft_revision", "published_draft_revision"} <= {
    column["name"] for column in inspector.get_columns("contents")
}
assert "permission_level" in {
    column["name"] for column in inspector.get_columns("content_versions")
}
```

- [ ] **Step 2: Run migration test and verify RED**

Run:

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest -q tests/test_migrations_phase2.py
```

Expected: new columns are absent.

- [ ] **Step 3: Add migration and model fields**

Migration upgrade:

```python
op.add_column("contents", sa.Column("draft_revision", sa.Integer(), nullable=False, server_default="1"))
op.add_column("contents", sa.Column("published_draft_revision", sa.Integer(), nullable=True))
op.add_column("content_versions", sa.Column("permission_level", sa.String(32), nullable=True))
op.execute("""
UPDATE content_versions
JOIN contents ON contents.id = content_versions.content_id
SET content_versions.permission_level = contents.permission_level
""")
op.alter_column("content_versions", "permission_level", nullable=False)
op.execute("""
UPDATE contents
SET published_draft_revision = draft_revision
WHERE current_version_id IS NOT NULL
""")
```

Use Alembic batch operations or SQLite-compatible correlated subqueries where required by migration tests. Downgrade drops the three columns.

Model fields:

```python
draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
published_draft_revision: Mapped[int | None] = mapped_column(Integer)
permission_level: Mapped[str] = mapped_column(String(32), nullable=False)
```

- [ ] **Step 4: Write publish invariant tests**

In `test_admin_content_phase4.py`:

```python
def test_saving_draft_does_not_create_version(client, admin_headers, db_session):
    content_id = create_draft(client, admin_headers)
    before = db_session.query(ContentVersion).count()
    client.patch(
        f"/api/admin/contents/{content_id}",
        json={"title": "修改后的草稿"},
        headers=admin_headers,
    )
    assert db_session.query(ContentVersion).count() == before


def test_repeating_publish_without_draft_change_is_idempotent(client, admin_headers, db_session):
    content_id = create_draft(client, admin_headers)
    first = client.post(f"/api/admin/contents/{content_id}/publish", headers=admin_headers)
    second = client.post(f"/api/admin/contents/{content_id}/publish", headers=admin_headers)
    assert first.json()["current_version_id"] == second.json()["current_version_id"]
    assert db_session.query(ContentVersion).filter_by(content_id=content_id).count() == 1
```

Add a republish test: patch draft, publish twice, assert exactly two versions, first chunks inactive, second chunks active, and version permission snapshots retain their publication-time values.

- [ ] **Step 5: Run content tests and verify RED**

Run:

```powershell
..\.venv\Scripts\python.exe -m pytest -q tests/test_admin_content_phase4.py
```

Expected: repeated publish creates two versions and permission snapshot is missing.

- [ ] **Step 6: Implement draft revision and row-locked publish**

In `update_content`, increment `draft_revision` only when at least one stored draft field changes.

In `publish_content`:

```python
content = db.scalar(
    select(Content).where(Content.id == content_id).with_for_update()
)
if content is None:
    raise not_found("内容不存在。")
if (
    content.current_version is not None
    and content.published_draft_revision == content.draft_revision
):
    return content.current_version

version = ContentVersion(
    content=content,
    version_no=next_version_no(content),
    title=content.title,
    summary=content.draft_summary,
    body=content.draft_body,
    structured_payload=content.draft_payload,
    permission_level=content.permission_level,
    published_at=now,
    effective_at=now,
    created_by=content.created_by,
)
content.published_draft_revision = content.draft_revision
```

History response uses `version.permission_level`.

- [ ] **Step 7: Write frontend pending and cancel tests**

In `admin-content-phase9.test.ts`, use a deferred publish Promise. Click publish twice and assert `post` is called once and the button is disabled while pending. Mock `window.confirm` false and assert no publish request.

- [ ] **Step 8: Run frontend tests and verify RED**

Run:

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm vitest run tests/admin-content-phase9.test.ts
```

Expected: two clicks create two requests or the button remains enabled.

- [ ] **Step 9: Implement per-content pending actions**

In `ContentListPage.vue`:

```ts
const pendingActions = reactive<Record<number, 'publish' | 'offline' | 'retry' | undefined>>({})

function isPending(item: AdminContent) {
  return Boolean(pendingActions[item.id])
}
```

Set and clear the action in `try/finally`; return immediately if already pending. Disable all mutation buttons for the item and display `发布中`, `下线中`, or `重试中`.

- [ ] **Step 10: Run focused tests and verify GREEN**

Run:

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest -q tests/test_migrations_phase2.py tests/test_admin_content_phase4.py
cd E:\WeView\work4\frontend
corepack.cmd pnpm vitest run tests/admin-content-phase9.test.ts
```

Expected: migration, backend invariants and frontend pending tests pass.

## Task 7: Test data audit and UTF-8 seed

**Files:**

- Create: `backend/app/cli/audit_test_data.py`
- Create: `backend/tests/test_test_data_audit.py`
- Modify: `docs/seed-phase8-manual-data.py`
- Modify: `backend/tests/test_documentation_phase11.py`

- [ ] **Step 1: Write failing audit tests**

Test pure classification:

```python
def test_audit_matches_only_known_test_records():
    assert classify_title("Phase45 Must Read General") == "phase45"
    assert classify_title("阶段8手测：基础开场白") == "phase8"
    assert classify_title("??8??????") == "mojibake"
    assert classify_title("客户正式业务话术") is None
```

Test dry-run leaves rows unchanged, while `execute=True` deletes only matching test quiz/content/user records.

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest -q tests/test_test_data_audit.py
```

Expected: module is missing.

- [ ] **Step 3: Implement the dry-run CLI**

Define explicit prefixes:

```python
KNOWN_TITLE_PREFIXES = ("Phase45 ", "阶段8手测：", "E2E ")
KNOWN_USER_PREFIXES = ("phase45_", "phase8_manual_", "phase10_")

def classify_title(value: str) -> str | None:
    if value.startswith("Phase45 "):
        return "phase45"
    if value.startswith("阶段8手测：") or value.startswith("阶段8手测题"):
        return "phase8"
    if value.startswith("E2E "):
        return "e2e"
    if value.startswith("??8") and "?" in value:
        return "mojibake"
    return None
```

CLI accepts `--execute`; without it, print IDs, titles and classifications only. Delete dependent quiz/chunk/vector/version records only for confirmed content IDs. Do not call `drop_all`, truncate tables, or delete unclassified rows.

- [ ] **Step 4: Make the seed update its own records**

In `seed-phase8-manual-data.py`, compare existing content by exact stable title. Update draft fields and publish only when the current published snapshot differs. Ensure a full-level quiz question is created with a Chinese literal source file.

- [ ] **Step 5: Run and verify GREEN**

Run:

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest -q tests/test_test_data_audit.py tests/test_documentation_phase11.py
```

Expected: classification and dry-run safety pass.

## Task 8: Deterministic E2E fixture and Playwright regression

**Files:**

- Modify: `backend/app/e2e_fixture.py`
- Modify: `backend/tests/test_e2e_fixture_phase10.py`
- Modify: `frontend/e2e/mvp-smoke.spec.ts`

- [ ] **Step 1: Extend fixture tests first**

Assert fixture contains:

- a general price-objection standard script containing L-A-C-T;
- a full battery-technology must-read containing `6000-8000`;
- a general must-read quiz relation;
- a full quiz relation;
- deterministic fake embeddings for hit, miss and race questions.

Run:

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest -q tests/test_e2e_fixture_phase10.py
```

Expected: new fixture keys/content are absent.

- [ ] **Step 2: Implement deterministic semantic routing**

In `E2EDashScopeClient.embed_text`, return distinct orthogonal vectors for price objection, cycle life, general hit, race questions and miss. In `generate_answer`, return answer text derived from the question so stale responses are observable.

- [ ] **Step 3: Add Playwright tests**

Add tests that:

1. Submit three questions rapidly and assert final question and answer both refer to the third.
2. Assert general user price objection returns L-A-C-T.
3. Assert general user cannot see or source the full battery content.
4. Assert full user cycle-life question returns `6000-8000`.
5. Copy recommended speech, full entry and AI answer, then read clipboard.
6. Assert general quiz contains no full question and full quiz contains at least one.
7. Submit quiz items linked to must-read and scripts and assert correct URLs.
8. Create draft, save again, publish twice, edit, republish, check exactly v1/v2, then offline and verify employee/RAG invisibility.

- [ ] **Step 4: Run Playwright and fix only observed failures**

Run:

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm test:e2e
```

Expected: all existing and new E2E tests pass.

## Task 9: Documentation and permission contract

**Files:**

- Modify: `docs/测试prompt.md`
- Modify: `docs/frontend-testing-manual.md`
- Modify: `docs/local-development.md`
- Modify: `memory-bank/architecture.md`

- [ ] **Step 1: Correct the cycle-life acceptance account**

Change test 5A.6 from `es_general` to `es_full`. Add an explicit assertion that `es_general` must not receive the full technology report or `6000-8000` source.

- [ ] **Step 2: Remove the committed plaintext manual password**

Restore `docs/frontend-testing-manual.md` to:

```powershell
$env:INITIAL_ADMIN_PASSWORD='<本次手测密码>'
```

Do not include the previously present value elsewhere.

- [ ] **Step 3: Document seed and cleanup boundaries**

Add commands:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m app.cli.audit_test_data
.\.venv\Scripts\python.exe -m app.cli.audit_test_data --execute
```

Explain that the first command is mandatory dry-run review and that E2E SQLite, development seed and real acceptance data are separate.

- [ ] **Step 4: Update architecture memory**

Record:

- AbortController plus request sequence.
- Stable labelled chunk text and query expansion.
- Relative source score window.
- Quiz full-question reservation and related content type.
- Draft revision publish idempotency and version permission snapshot.
- Clipboard fallback.
- DashScope retry classes.
- Dry-run test-data audit.
- New test counts after final verification.

## Task 10: Full verification and real browser regression

**Files:**

- Verify all changed files.

- [ ] **Step 1: Run backend suite**

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m pytest -q
```

Expected: zero failures. If the previous order-dependent index test reappears, inspect dependency override leakage before changing product code.

- [ ] **Step 2: Run frontend unit suite**

```powershell
cd E:\WeView\work4\frontend
corepack.cmd pnpm test:unit
```

Expected: zero failures.

- [ ] **Step 3: Run frontend production build**

```powershell
corepack.cmd pnpm build
```

Expected: TypeScript check and Vite build exit 0.

- [ ] **Step 4: Run Playwright**

```powershell
corepack.cmd pnpm test:e2e
```

Expected: zero failures.

- [ ] **Step 5: Apply the migration to the real local database**

After confirming the configured target is the project local MySQL:

```powershell
cd E:\WeView\work4\backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

Do not print `.env` or connection secrets.

- [ ] **Step 6: Audit test data before any deletion**

Run only dry-run first:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python.exe -m app.cli.audit_test_data
```

Review the exact IDs. Do not use `--execute` unless every row is an identified project test row.

- [ ] **Step 7: Reindex affected current content**

Use existing administrator retry-index APIs for the known price objection, return period, cycle-life and other seeded content. Confirm no new `content_versions` rows are created.

- [ ] **Step 8: Verify with the in-app browser**

At `http://localhost:5173` verify visible page state and URLs for:

- rapid three-question sequence;
- price objection L-A-C-T;
- unrelated weather miss;
- general-user full-content denial;
- full-user `6000-8000`;
- three copy entries and clipboard text;
- general/full quiz difference;
- must-read/script related links;
- draft, repeated publish, republish, history and offline.

- [ ] **Step 9: Verify with Chrome if available**

Check Chrome extension connectivity. If unavailable because the Codex Chrome Extension is not installed/enabled, report that exact environment blocker and do not claim Chrome verification.

- [ ] **Step 10: Inspect final Git diff**

```powershell
git status --short
git diff --check
git diff --stat
```

Confirm no `.env`, API key, database password, JWT secret, temporary DB, screenshot, cache or unrelated formatting is included.
