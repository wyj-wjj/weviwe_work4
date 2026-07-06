<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

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
        }
      },
      controller.signal
    )
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  activeController?.abort()
  activeController = null
})
</script>

<template>
  <EmployeeLayout>
    <section class="ai-page">
      <h2>AI 问答结果</h2>
      <p v-if="question" class="ai-page__question">问题：{{ question }}</p>

      <AppState v-if="state === 'loading'" state="loading" :message="aiStateMessage" />
      <AppState v-else-if="state === 'empty'" state="empty" message="请输入要查询的问题" />
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
              <span>更新时间：{{ formatDateTime(source.updated_at) }}</span>
              <span>更新级别：{{ updateLevelLabel(source.update_level) }}</span>
              <span>可见范围：{{ scopeLabel(source.scope_type) }}</span>
              <a :href="sourceDetailPath(source.content_type, source.content_id)">查看来源</a>
            </article>
          </div>
        </section>
      </article>
    </section>
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
</style>
