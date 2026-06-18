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

const hasQuestions = computed(() => questions.value.length > 0)

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

async function loadQuiz() {
  state.value = 'loading'
  try {
    const response = await getQuiz()
    questions.value = response.items
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

async function submitAnswers() {
  if (isSubmitting.value) {
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
      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="!hasQuestions" state="empty" message="暂无可用测试题" />

      <form v-else class="quiz-page__form" @submit.prevent="submitAnswers">
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

.quiz-page__form {
  display: grid;
  gap: 14px;
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
