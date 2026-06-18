<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { askRag, type RagAnswerResponse } from '../../api/rag'
import AppState from '../../components/AppState.vue'
import CopyButton from '../../components/CopyButton.vue'
import EmployeeLayout from '../../components/EmployeeLayout.vue'
import { contentTypeLabel, formatDateTime, sourceDetailPath } from '../../utils/format'

const route = useRoute()
const answer = ref<RagAnswerResponse | null>(null)
const state = ref<'loading' | 'ready' | 'empty' | 'ai-unavailable' | 'service'>('loading')
let requestSequence = 0
let activeController: AbortController | null = null

const question = computed(() => {
  const queryQuestion = route.query.question
  return Array.isArray(queryQuestion) ? (queryQuestion[0] ?? '') : (queryQuestion ?? '')
})

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
      state.value = apiError.code === 'ai_unavailable' || apiError.status === 503 ? 'ai-unavailable' : 'service'
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  requestSequence += 1
  activeController?.abort()
  activeController = null
})
</script>

<template>
  <EmployeeLayout>
    <section class="ai-page">
      <h2>AI 问答结果</h2>
      <p v-if="question" class="ai-page__question">问题：{{ question }}</p>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'empty'" state="empty" message="请输入要查询的问题" />
      <AppState v-else-if="state === 'ai-unavailable'" state="ai-unavailable" />
      <AppState v-else-if="state === 'service'" state="service" />

      <article v-else-if="answer" class="ai-answer">
        <section>
          <h3>回答</h3>
          <p>{{ answer.answer }}</p>
          <CopyButton label="复制回答" :text="answer.answer" />
        </section>

        <section v-if="answer.hit && answer.sources.length > 0">
          <h3>来源</h3>
          <div class="source-list">
            <article v-for="source in answer.sources" :key="source.chunk_id" class="source-card">
              <strong>{{ source.title }}</strong>
              <span>{{ contentTypeLabel(source.content_type) }}</span>
              <span>更新时间：{{ formatDateTime(source.updated_at) }}</span>
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

.ai-answer p {
  line-height: 1.7;
  margin: 0 0 12px;
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
