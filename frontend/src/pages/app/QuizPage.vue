<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

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
    error.value = '请先完成所有题目'
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
            跟进最新
          </button>
          <button
            type="button"
            :class="{ active: mode === 'review' }"
            @click="changeMode('review')"
          >
            复习旧内容
          </button>
        </div>
        <label v-if="mode === 'review'">
          <span>分类</span>
          <select v-model="selectedCategory" @change="changeCategory">
            <option value="">全部</option>
            <option v-for="category in categories" :key="category" :value="category">
              {{ category }}
            </option>
          </select>
        </label>
        <div class="quiz-page__refresh">
          <button type="button" @click="loadQuiz">重新抽题</button>
          <span>题库较少时可能抽到相同题目</span>
        </div>
      </div>
      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="!hasQuestions" state="empty" message="暂无可用测试题" />

      <form v-else class="quiz-page__form" @submit.prevent="submitAnswers">
        <p class="quiz-page__progress">已答 {{ answeredCount }} / 共 {{ questions.length }} 题</p>
        <p v-if="error" class="quiz-page__error">{{ error }}</p>
        <article v-for="question in questions" :key="question.id" class="quiz-card">
          <h3>{{ question.question }}</h3>
          <label
            v-for="option in question.options"
            :key="optionValue(option)"
            class="quiz-card__option"
          >
            <input
              v-model="answers[question.id]"
              type="radio"
              :name="`question-${question.id}`"
              :value="optionValue(option)"
              :aria-label="`${question.question} ${optionValue(option)}`"
              :disabled="isSubmitted"
            />
            <span>{{ optionLabel(option) }}</span>
          </label>

          <section v-if="resultFor(question.id)" class="quiz-card__result">
            <strong>{{ resultFor(question.id)?.is_correct ? '回答正确' : '回答错误' }}</strong>
            <p>正确答案：{{ resultFor(question.id)?.correct_answer }}</p>
            <p v-if="resultFor(question.id)?.explanation">
              {{ resultFor(question.id)?.explanation }}
            </p>
            <RouterLink
              v-if="relatedPathFor(question.id)"
              :to="relatedPathFor(question.id) ?? ''"
            >
              查看关联话术
            </RouterLink>
          </section>
        </article>

        <button class="quiz-page__submit" type="submit" :disabled="isSubmitting">
          {{ isSubmitting ? '提交中' : '提交答案' }}
        </button>
      </form>
    </section>
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
</style>
