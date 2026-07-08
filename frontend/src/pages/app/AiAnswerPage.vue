<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { apiClient } from '../../api/client'
import { askRagStream, type RagSource } from '../../api/rag'
import AppState from '../../components/AppState.vue'
import CopyButton from '../../components/CopyButton.vue'
import EmployeeLayout from '../../components/EmployeeLayout.vue'
import { contentTypeLabel, formatDateTime, scopeLabel, sourceDetailPath, updateLevelLabel } from '../../utils/format'

const route = useRoute()
const answerText = ref('')
const sources = ref<RagSource[]>([])
const state = ref<'loading' | 'generating' | 'ready' | 'empty' | 'ai-unavailable' | 'service'>('loading')
const aiStateMessage = ref('')
let activeController: AbortController | null = null

const question = computed(() => {
  const queryQuestion = route.query.question
  return Array.isArray(queryQuestion) ? (queryQuestion[0] ?? '') : (queryQuestion ?? '')
})

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
    aiStateMessage.value = '正在检索标准话术并生成回答，请稍候。'

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
        },
        onDebug: (stage, data) => {
          console.log(`[RAG-DEBUG] ${stage}:`, data)
        },
      },
      controller.signal,
      true,
    )
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  activeController?.abort()
  activeController = null
})

// ---------- 浮窗详情 ----------
const detailModal = ref<{
  visible: boolean
  loading: boolean
  title: string
  body: string
  error: string
}>({
  visible: false,
  loading: false,
  title: '',
  body: '',
  error: '',
})

async function openSourceDetail(contentType: string, contentId: number) {
  detailModal.value = { visible: true, loading: true, title: '', body: '', error: '' }
  const apiPath = sourceDetailPath(contentType, contentId)
  try {
    const response = await apiClient.get<any>(apiPath)
    const data = response.data
    detailModal.value.title = data.title || ''
    detailModal.value.body = data.body || data.copy_text || ''
    detailModal.value.loading = false
  } catch {
    detailModal.value.error = '加载失败，请稍后重试。'
    detailModal.value.loading = false
  }
}

function closeDetail() {
  detailModal.value.visible = false
}
// ----------------------------------
</script>

<template>
  <EmployeeLayout>
    <section class="ai-page">
      <h2>AI 问答助手</h2>
      <p v-if="question" class="ai-page__question">问题：{{ question }}</p>

      <AppState v-if="state === 'loading'" state="loading" :message="aiStateMessage" />
      <AppState v-else-if="state === 'empty'" state="empty" message="请输入需要查询的问题" />
      <AppState v-else-if="state === 'ai-unavailable'" state="ai-unavailable" :message="aiStateMessage" />
      <AppState v-else-if="state === 'service'" state="service" :message="aiStateMessage" />

      <article v-else-if="state === 'generating' || state === 'ready'" class="ai-answer">
        <section>
          <h3>回答</h3>
          <p class="answer-text">{{ answerText }}<span v-if="state === 'generating'" class="cursor"></span></p>
          <CopyButton v-if="state === 'ready'" label="复制回答" :text="answerText" />
        </section>

        <section v-if="sources.length > 0">
          <h3>来源</h3>
          <div class="source-list">
            <article v-for="source in sources" :key="source.chunk_id" class="source-card">
              <strong>{{ source.title }}</strong>
              <span>{{ contentTypeLabel(source.content_type) }}</span>
              <span>发布时间：{{ formatDateTime(source.updated_at) }}</span>
              <span>更新级别：{{ updateLevelLabel(source.update_level) }}</span>
              <span>可见范围：{{ scopeLabel(source.scope_type) }}</span>
              <button
                type="button"
                class="source-card__detail-btn"
                @click="openSourceDetail(source.content_type, source.content_id)"
              >
                查看来源
              </button>
            </article>
          </div>
        </section>
      </article>
    </section>

    <!-- 浮窗详情 -->
    <Teleport to="body">
      <div v-if="detailModal.visible" class="detail-overlay" @click.self="closeDetail">
        <div class="detail-modal">
          <div class="detail-modal__header">
            <h3>{{ detailModal.title || '关联话术' }}</h3>
            <button type="button" class="detail-modal__close" @click="closeDetail">×</button>
          </div>
          <div v-if="detailModal.loading" class="detail-modal__loading">加载中...</div>
          <div v-else-if="detailModal.error" class="detail-modal__error">{{ detailModal.error }}</div>
          <pre v-else class="detail-modal__body">{{ detailModal.body }}</pre>
        </div>
      </div>
    </Teleport>
  </EmployeeLayout>
</template>

<style scoped>
.ai-page h2 {
  font-size: 22px;
  margin: 0 0 10px;
}

.ai-page__question {
  color: #52606d;
  margin: 0 0 16px;
}

.ai-answer {
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  display: grid;
  gap: 20px;
  padding: 20px;
}

.ai-answer h3 {
  font-size: 17px;
  margin: 0 0 8px;
}

.answer-text {
  line-height: 1.7;
  margin: 0 0 12px;
  white-space: pre-wrap;
}

.cursor {
  display: inline-block;
  width: 8px;
  height: 16px;
  background-color: #52606d;
  vertical-align: middle;
  margin-left: 4px;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.source-list {
  display: grid;
  gap: 10px;
}

.source-card {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  display: grid;
  gap: 6px;
  padding: 12px;
}

.source-card span {
  color: #52606d;
}

.source-card__detail-btn {
  background: transparent;
  border: 0;
  color: #1d4ed8;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  padding: 0;
  text-align: left;
  text-decoration: underline;
}

.source-card__detail-btn:hover {
  color: #1e40af;
}

/* ---------- 浮窗 ---------- */
.detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
}

.detail-modal {
  background: #ffffff;
  border-radius: 10px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
  max-height: 80vh;
  max-width: 680px;
  width: 90vw;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-modal__header {
  align-items: center;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  padding: 16px 20px;
}

.detail-modal__header h3 {
  font-size: 18px;
  margin: 0;
}

.detail-modal__close {
  background: transparent;
  border: 0;
  cursor: pointer;
  font-size: 24px;
  line-height: 1;
  padding: 0 4px;
  color: #64748b;
}

.detail-modal__close:hover {
  color: #1e293b;
}

.detail-modal__loading,
.detail-modal__error {
  padding: 24px 20px;
  color: #64748b;
}

.detail-modal__error {
  color: #b42318;
}

.detail-modal__body {
  flex: 1;
  font-family: inherit;
  font-size: 15px;
  line-height: 1.7;
  margin: 0;
  overflow-y: auto;
  padding: 20px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
