<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { apiClient } from '../../api/client'
import { getQuiz, submitQuiz, type QuizQuestion, type QuizSubmitResult } from '../../api/quiz'
import AppState from '../../components/AppState.vue'
import EmployeeLayout from '../../components/EmployeeLayout.vue'
import { sourceDetailPath } from '../../utils/format'

const questions = ref<QuizQuestion[]>([])
const results = ref<QuizSubmitResult[]>([])
const answers = reactive<Record<number, string>>({})
const state = ref<'loading' | 'ready' | 'service'>('loading')
const isSubmitting = ref(false)
const mode = ref<'latest' | 'review'>('latest')
const selectedCategory = ref('')
const error = ref('')

const hasQuestions = computed(() => questions.value.length > 0)
const isSubmitted = computed(() => results.value.length > 0)
const answeredCount = computed(
  () => questions.value.filter((question) => Boolean(answers[question.id])).length,
)
const categories = computed(() => {
  const merged = new Set<string>()
  for (const question of questions.value) {
    const category = question.related_content_category?.trim()
    if (category) {
      merged.add(category)
    }
  }
  return Array.from(merged)
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

function apiPathFor(questionId: number): string | null {
  const result = resultFor(questionId)
  if (!result?.related_content_id || !result.related_content_type) {
    return null
  }
  return sourceDetailPath(result.related_content_type, result.related_content_id)
}

async function openScriptDetail(questionId: number) {
  const apiPath = apiPathFor(questionId)
  if (!apiPath) return

  detailModal.value = { visible: true, loading: true, title: '', body: '', error: '' }
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

function optionValue(option: string | { label?: string; value?: string }): string {
  return typeof option === 'string' ? option : (option.value ?? option.label ?? '')
}

function optionLabel(option: string | { label?: string; value?: string }): string {
  return typeof option === 'string' ? option : (option.label ?? option.value ?? '')
}

function resultFor(questionId: number) {
  return results.value.find((result) => result.question_id === questionId)
}

function relatedPathFor(questionId: number): string | null {
  const result = resultFor(questionId)
  if (!result?.related_content_id || !result.related_content_type) {
    return null
  }
  return sourceDetailPath(result.related_content_type, result.related_content_id)
}

function createRefreshSeed(): string {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

async function loadQuiz() {
  state.value = 'loading'
  error.value = ''
  results.value = []
  for (const questionId of Object.keys(answers)) {
    delete answers[Number(questionId)]
  }
  try {
    const requestParams: Parameters<typeof getQuiz>[0] = {
      mode: mode.value,
      refresh_seed: createRefreshSeed(),
    }
    if (mode.value === 'review' && selectedCategory.value) {
      requestParams.category = selectedCategory.value
    }
    const response = await getQuiz(requestParams)
    questions.value = response.items
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

async function changeMode(nextMode: 'latest' | 'review') {
  mode.value = nextMode
  selectedCategory.value = ''
  await loadQuiz()
}

async function changeCategory() {
  await loadQuiz()
}

async function submitAnswers() {
  if (isSubmitting.value) {
    return
  }
  error.value = ''
  if (answeredCount.value < questions.value.length) {
    error.value = '请回答所有题目'
    return
  }

  isSubmitting.value = true
  try {
    const response = await submitQuiz({
      answers: Object.entries(answers).map(([questionId, selectedAnswer]) => ({
        question_id: Number(questionId),
        selected_answer: selectedAnswer,
      })),
    })
    results.value = response.results
  } finally {
    isSubmitting.value = false
  }
}

onMounted(loadQuiz)
</script>

<template>
  <EmployeeLayout>
    <section class="quiz-page">
      <h2>巩固测试</h2>
      <div class="quiz-page__toolbar">
        <div class="quiz-page__modes">
          <button
            type="button"
            :class="{ active: mode === 'latest' }"
            @click="changeMode('latest')"
          >
            最新
          </button>
          <button
            type="button"
            :class="{ active: mode === 'review' }"
            @click="changeMode('review')"
          >
            复习
          </button>
        </div>
        <label v-if="mode === 'review' && categories.length">
          分类：
          <select :value="selectedCategory" @change="changeCategory()">
            <option value="">全部</option>
            <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
          </select>
        </label>
        <div class="quiz-page__refresh">
          <button type="button" @click="loadQuiz()">刷新题目</button>
        </div>
      </div>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="!hasQuestions" state="empty" message="暂无可练习题" />

      <form v-else class="quiz-page__form" @submit.prevent="submitAnswers">
        <p class="quiz-page__progress">已回答 {{ answeredCount }} / {{ questions.length }}</p>
        <p v-if="error" class="quiz-page__error">{{ error }}</p>

        <article v-for="question in questions" :key="question.id" class="quiz-card">
          <h3>{{ question.question }}</h3>
          <label
            v-for="option in question.options"
            :key="optionValue(option)"
            class="quiz-card__option"
          >
            <input
              type="radio"
              :name="'question-' + question.id"
              :value="optionValue(option)"
              :checked="answers[question.id] === optionValue(option)"
              :disabled="isSubmitted"
              @change="answers[question.id] = optionValue(option)"
            />
            <span>{{ optionLabel(option) }}</span>
          </label>

          <section v-if="resultFor(question.id)" class="quiz-card__result">
            <strong>{{ resultFor(question.id)?.is_correct ? '回答正确' : '回答错误' }}</strong>
            <p>正确答案：{{ resultFor(question.id)?.correct_answer }}</p>
            <p v-if="resultFor(question.id)?.explanation">
              {{ resultFor(question.id)?.explanation }}
            </p>
            <button
              v-if="relatedPathFor(question.id)"
              type="button"
              class="quiz-card__detail-btn"
              @click="openScriptDetail(question.id)"
            >
              查看关联话术
            </button>
          </section>
        </article>

        <button class="quiz-page__submit" type="submit" :disabled="isSubmitting">
          {{ isSubmitting ? '提交中' : '提交答案' }}
        </button>
      </form>
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
.quiz-page h2 {
  font-size: 22px;
  margin: 0 0 16px;
}

.quiz-page__toolbar {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
}

.quiz-page__modes {
  display: flex;
  gap: 8px;
}

.quiz-page__toolbar button,
.quiz-page__toolbar select {
  border: 1px solid #bcccdc;
  border-radius: 6px;
  background: #ffffff;
  cursor: pointer;
  font: inherit;
  min-height: 36px;
  padding: 0 12px;
}

.quiz-page__toolbar button.active {
  border-color: #1d4ed8;
  background: #dbeafe;
  color: #1e3a8a;
  font-weight: 700;
}

.quiz-page__toolbar label {
  display: grid;
  gap: 6px;
}

.quiz-page__refresh {
  align-items: center;
  display: flex;
  gap: 8px;
}

.quiz-page__refresh span {
  color: #64748b;
  font-size: 13px;
}

.quiz-page__form {
  display: grid;
  gap: 14px;
}

.quiz-page__progress {
  color: #52606d;
  margin: 0;
}

.quiz-page__error {
  color: #b42318;
  font-weight: 700;
  margin: 0;
}

.quiz-card {
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  display: grid;
  gap: 10px;
  padding: 16px;
}

.quiz-card h3 {
  font-size: 17px;
  margin: 0;
}

.quiz-card__option {
  align-items: center;
  display: flex;
  gap: 8px;
}

.quiz-card__result {
  background: #f8fafc;
  border-radius: 6px;
  display: grid;
  gap: 6px;
  padding: 12px;
}

.quiz-card__result p {
  margin: 0;
}

.quiz-card__detail-btn {
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

.quiz-card__detail-btn:hover {
  color: #1e40af;
}

.quiz-page__submit {
  border: 0;
  border-radius: 6px;
  background: #1d4ed8;
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  min-height: 42px;
}

.quiz-page__submit:disabled {
  cursor: wait;
  opacity: 0.7;
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
