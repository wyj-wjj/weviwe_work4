# RAG Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completely replace the `fast_extractive` RAG mode with a true LLM streaming (Server-Sent Events) answer mode to reduce Time-To-First-Token (TTFT) and improve user experience.

**Architecture:** 
1. `DashScopeHttpClient` will get a new `generate_answer_stream` method using `httpx.Client.stream` to parse SSE events from DashScope OpenAI-compatible API.
2. `rag_answer_service.py` will use this new stream and yield its own SSE events (`sources`, `content`, `done`, `error`).
3. The `/api/app/rag/ask` route will return a `StreamingResponse` from FastAPI.
4. The frontend will use `fetch` with `ReadableStream` to parse the SSE stream and incrementally update the UI with a typewriter effect.

**Tech Stack:** FastAPI `StreamingResponse`, `httpx` stream, Vue 3, native `fetch` API.

## Global Constraints

- Backend uses synchronous `SQLAlchemy 2.x` and `httpx.Client` (no `asyncio`).
- FastAPI `StreamingResponse` must work with a synchronous generator.
- DashScope uses OpenAI-compatible `/chat/completions` with `stream: True`.
- No new third-party libraries; use standard `fetch` API for frontend SSE parsing.

---

### Task 1: Implement DashScope Streaming Client

**Files:**
- Modify: `E:\WeView\work4\backend\app\integrations\dashscope.py`

**Interfaces:**
- Consumes: Existing `DashScopeHttpClient` configurations.
- Produces: `FakeDashScopeClient.generate_answer_stream` and `DashScopeHttpClient.generate_answer_stream` yielding string chunks.

- [ ] **Step 1: Write minimal implementation for FakeDashScopeClient**
In `E:\WeView\work4\backend\app\integrations\dashscope.py`, add `generate_answer_stream` to `FakeDashScopeClient`:
```python
    def generate_answer_stream(
        self,
        *,
        question: str,
        contexts: list[dict[str, Any]],
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.chat_requests.append(
            {
                "question": question,
                "contexts": contexts,
                "model_name": model_name,
                "timeout_seconds": timeout_seconds,
                "stream": True,
            }
        )
        if self.chat_error is not None:
            raise self.chat_error
        
        words = self.chat_answer.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
```

- [ ] **Step 2: Write minimal implementation for DashScopeHttpClient**
In `E:\WeView\work4\backend\app\integrations\dashscope.py`, add `generate_answer_stream` to `DashScopeHttpClient`:
```python
    def generate_answer_stream(
        self,
        *,
        question: str,
        contexts: list[dict[str, Any]],
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ):
        source_blocks = []
        for index, context in enumerate(contexts, start=1):
            source = context.get("source") if isinstance(context.get("source"), dict) else {}
            title = source.get("title") or f"来源 {index}"
            text = context.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            source_blocks.append(f"[来源 {index}] {title}\n{text.strip()}")
        if not source_blocks:
            raise ProviderResponseError("No authorized context was provided for answer generation.")

        payload = {
            "model": model_name or self.settings.dashscope_chat_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是企业官方话术助手。只能依据提供的已授权来源回答，"
                        "不得补充来源中没有的业务结论，不得推测，不得泄露未提供的内容。"
                        "先直接回答用户问题，并覆盖来源中与问题直接相关的关键数字、条件和限制。"
                        "不要机械罗列与问题无关的来源内容。"
                        "如果来源不足以回答，应明确说明现有来源不足。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"用户问题：{question}\n\n"
                        "以下内容均已通过当前账号权限和有效状态校验：\n\n"
                        + "\n\n".join(source_blocks)
                    ),
                },
            ],
            "stream": True,
            "stream_options": {"include_usage": True}
        }
        
        url = f"{self.settings.dashscope_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        timeout = timeout_seconds or self.settings.dashscope_http_timeout_seconds
        
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    raise ProviderResponseError(f"DashScope returned HTTP {response.status_code}.")
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if not data_str or data_str == "[DONE]":
                            continue
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices and "delta" in choices[0]:
                                content = choices[0]["delta"].get("content")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
```

- [ ] **Step 3: Commit**
```bash
git add backend/app/integrations/dashscope.py
git commit -m "feat: add streaming support to DashScope client"
```

---

### Task 2: Update RAG Answer Service to Yield SSE

**Files:**
- Modify: `E:\WeView\work4\backend\app\services\rag_answer_service.py`

**Interfaces:**
- Consumes: `dashscope_client.generate_answer_stream`
- Produces: `answer_question` returns a generator yielding formatted JSON strings.

- [ ] **Step 1: Write minimal implementation**
In `E:\WeView\work4\backend\app\services\rag_answer_service.py`, modify `answer_question` to act as a generator and remove `build_fast_answer`/`compact_source_text`:
```python
import json

def answer_question(
    db: Session,
    *,
    user: User,
    question: str,
    dashscope_client,
    milvus_client,
    settings: Settings | None = None,
):
    resolved_settings = settings or Settings()
    try:
        question_embedding = dashscope_client.embed_text(retrieval_question(question))
        vector_hits = milvus_client.search(
            resolved_settings.milvus_collection_name,
            query_vector=question_embedding.vector,
            allowed_permission_levels=visible_levels_for(user),
            visible_department_id=user.department_id,
            include_all_department_scoped=can_view_all_department_scopes(user),
            top_k=resolved_settings.rag_top_k,
        )
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': '智能问答暂不可用，请稍后重试。'})}\n\n"
        return

    keyword_hits = keyword_search_hits(
        db,
        question=question,
        user=user,
        top_k=resolved_settings.rag_top_k,
    )
    hits = merge_retrieval_hits(vector_hits, keyword_hits)
    contexts = load_authorized_contexts(
        db,
        hits=hits,
        user=user,
        min_score=resolved_settings.rag_similarity_threshold,
    )
    if not contexts:
        record_missed_question(db, question=question, user=user)
        yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
        yield f"data: {json.dumps({'type': 'content', 'text': MISSED_MESSAGE})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    sources = [context["source"] for context in contexts]
    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

    try:
        for chunk in dashscope_client.generate_answer_stream(
            question=question,
            contexts=contexts,
        ):
            yield f"data: {json.dumps({'type': 'content', 'text': chunk})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': '生成回答时发生错误，请稍后重试。'})}\n\n"
        return
        
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
```
*(Also remove `build_fast_answer` and `compact_source_text` as they are no longer used).*

- [ ] **Step 2: Commit**
```bash
git add backend/app/services/rag_answer_service.py
git commit -m "feat: convert answer_question to yield SSE streaming events"
```

---

### Task 3: Update FastAPI Route and Tests

**Files:**
- Modify: `E:\WeView\work4\backend\app\api\routes\rag.py`
- Modify: `E:\WeView\work4\backend\tests\test_rag_phase6.py`

**Interfaces:**
- Consumes: `answer_question` generator
- Produces: `StreamingResponse` with `media_type="text/event-stream"`

- [x] **Step 1: Write minimal implementation in `rag.py`**
In `E:\WeView\work4\backend\app\api\routes\rag.py`:
```python
from fastapi.responses import StreamingResponse

@router.post("/api/app/rag/ask")
def app_ask_rag(
    payload: RagAskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    dashscope_client=Depends(get_dashscope_client),
    milvus_client=Depends(get_milvus_client),
) -> StreamingResponse:
    generator = answer_question(
        db,
        user=current_user,
        question=payload.question,
        dashscope_client=dashscope_client,
        milvus_client=milvus_client,
    )
    return StreamingResponse(generator, media_type="text/event-stream")
```

- [x] **Step 2: Fix failing backend tests**
Modify `E:\WeView\work4\backend\tests\test_rag_phase6.py` to handle generators. Instead of `assert result["hit"] is True`, read the generator/StreamingResponse:
```python
# Helper to read generator in tests:
def consume_stream(generator):
    events = []
    for item in generator:
        if item.startswith("data: "):
            events.append(json.loads(item[6:].strip()))
    return events
```
Update tests like `test_rag_missed_question_when_no_hits` and `test_rag_returns_answer_when_hit` to verify the `events` list.

- [x] **Step 3: Commit**
```bash
git add backend/app/api/routes/rag.py backend/tests/test_rag_phase6.py
git commit -m "feat: use StreamingResponse for RAG endpoint and fix tests"
```

---

### Task 4: Frontend API - Fetch SSE parser

**Files:**
- Modify: `E:\WeView\work4\frontend\src\api\rag.ts`

**Interfaces:**
- Consumes: SSE `/api/app/rag/ask`
- Produces: `askRagStream` with callbacks

- [ ] **Step 1: Write minimal implementation**
In `E:\WeView\work4\frontend\src\api\rag.ts`, remove `askRag` and replace with:
```typescript
export interface RagStreamCallbacks {
  onSources?: (sources: RagSource[]) => void;
  onContent?: (text: string) => void;
  onError?: (error: string) => void;
  onDone?: () => void;
}

export async function askRagStream(
  question: string,
  callbacks: RagStreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const token = localStorage.getItem('token') || sessionStorage.getItem('token');
  try {
    const response = await fetch('/api/app/rag/ask', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ question }),
      signal
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      callbacks.onError?.(errorData.message || '服务异常，请稍后重试');
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      callbacks.onError?.('当前环境不支持流式读取');
      return;
    }

    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'sources') {
              callbacks.onSources?.(data.sources);
            } else if (data.type === 'content') {
              callbacks.onContent?.(data.text);
            } else if (data.type === 'error') {
              callbacks.onError?.(data.message);
            } else if (data.type === 'done') {
              callbacks.onDone?.();
            }
          } catch (e) {
            console.error('SSE JSON parse error', e);
          }
        }
      }
    }
  } catch (error: any) {
    if (error.name === 'AbortError') return;
    callbacks.onError?.('网络异常，请重试');
  }
}
```

- [ ] **Step 2: Commit**
```bash
git add frontend/src/api/rag.ts
git commit -m "feat: frontend fetch SSE parser for RAG streaming"
```

---

### Task 5: Frontend UI - Typewriter Effect

**Files:**
- Modify: `E:\WeView\work4\frontend\src\pages\app\AiAnswerPage.vue`

**Interfaces:**
- Consumes: `askRagStream`
- Produces: Interactive typewriter UI

- [ ] **Step 1: Write minimal implementation**
Update `AiAnswerPage.vue` to handle the stream:
```vue
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { askRagStream, type RagSource } from '../../api/rag'
// ... other imports

const route = useRoute()
const answerText = ref('')
const sources = ref<RagSource[]>([])
const state = ref<'loading' | 'generating' | 'ready' | 'empty' | 'ai-unavailable' | 'service'>('loading')
const aiStateMessage = ref('')
let activeController: AbortController | null = null

// ... question computed property ...

watch(
  [question, () => route.query.request],
  async ([currentQuestion]) => {
    activeController?.abort()
    activeController = null
    answerText.value = ''
    sources.value = []

    const normalizedQuestion = currentQuestion.trim()
    if (!normalizedQuestion) {
      state.value = 'empty'
      return
    }

    const controller = new AbortController()
    activeController = controller
    state.value = 'loading'
    aiStateMessage.value = '正在检索标准话术...'

    await askRagStream(
      normalizedQuestion,
      {
        onSources: (s) => {
          sources.value = s
          state.value = 'generating'
        },
        onContent: (text) => {
          answerText.value += text
        },
        onError: (msg) => {
          aiStateMessage.value = msg
          state.value = 'service'
        },
        onDone: () => {
          state.value = 'ready'
        }
      },
      controller.signal
    )
  },
  { immediate: true },
)

// ... template updates ...
```
In template:
- Use `answerText.value` for answer.
- Update `<article v-else-if="state === 'generating' || state === 'ready'">` to show the typing text and sources.
- Add markdown rendering or just `white-space: pre-wrap` for `answerText.value`.

- [ ] **Step 2: Commit**
```bash
git add frontend/src/pages/app/AiAnswerPage.vue
git commit -m "feat: frontend AI Answer page typewriter effect"
```
