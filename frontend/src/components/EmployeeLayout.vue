<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const question = ref('')
const questionError = ref('')

const displayName = computed(() => auth.user?.display_name ?? auth.user?.username ?? '')

function logout() {
  auth.logout()
  router.push('/login')
}

function submitQuestion() {
  const normalizedQuestion = question.value.trim()
  questionError.value = ''

  if (!normalizedQuestion) {
    questionError.value = '请输入要查询的问题'
    return
  }

  router.push({
    name: 'employee-ai-answer',
    query: {
      question: normalizedQuestion,
    },
  })
}
</script>

<template>
  <main class="employee-layout">
    <header class="employee-layout__header">
      <div>
        <p class="employee-layout__eyebrow">企业话术培训</p>
        <h1>员工首页</h1>
      </div>
      <div class="employee-layout__user">
        <span>{{ displayName }}</span>
        <button type="button" @click="logout">退出登录</button>
      </div>
    </header>

    <form class="employee-layout__search" aria-label="AI 问答" @submit.prevent="submitQuestion">
      <label for="employee-ai-question">AI 问题</label>
      <div class="employee-layout__search-row">
        <input
          id="employee-ai-question"
          v-model="question"
          name="question"
          type="search"
          placeholder="输入你想查询的话术问题"
        />
        <button type="submit">提问</button>
      </div>
      <p v-if="questionError" class="employee-layout__error">{{ questionError }}</p>
    </form>

    <nav class="employee-layout__nav" aria-label="员工核心入口">
      <RouterLink to="/app/must-reads">最新必读</RouterLink>
      <RouterLink to="/app/scripts">标准话术</RouterLink>
      <RouterLink to="/app/quiz">巩固测试</RouterLink>
    </nav>

    <section class="employee-layout__content">
      <slot />
    </section>
  </main>
</template>

<style scoped>
.employee-layout {
  margin: 0 auto;
  max-width: 960px;
  min-height: 100vh;
  padding: 20px;
}

.employee-layout__header,
.employee-layout__user,
.employee-layout__search-row,
.employee-layout__nav {
  display: flex;
  align-items: center;
}

.employee-layout__header {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.employee-layout__eyebrow {
  color: #52606d;
  font-size: 14px;
  margin: 0 0 4px;
}

.employee-layout h1 {
  font-size: 26px;
  line-height: 1.2;
  margin: 0;
}

.employee-layout__user {
  gap: 10px;
  white-space: nowrap;
}

.employee-layout__user button,
.employee-layout__search button {
  border: 1px solid #1d4ed8;
  border-radius: 6px;
  background: #1d4ed8;
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  min-height: 40px;
  padding: 0 14px;
}

.employee-layout__search {
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  padding: 16px;
}

.employee-layout__search label {
  display: block;
  font-weight: 700;
  margin-bottom: 8px;
}

.employee-layout__search-row {
  gap: 10px;
}

.employee-layout__search input {
  border: 1px solid #bcccdc;
  border-radius: 6px;
  flex: 1;
  font: inherit;
  min-height: 40px;
  min-width: 0;
  padding: 0 12px;
}

.employee-layout__error {
  color: #be123c;
  font-size: 14px;
  margin: 8px 0 0;
}

.employee-layout__nav {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 16px 0;
}

.employee-layout__nav a {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #ffffff;
  color: #1f2933;
  font-weight: 700;
  min-height: 64px;
  padding: 20px 16px;
  text-align: center;
  text-decoration: none;
}

.employee-layout__nav a:hover {
  border-color: #3b82f6;
  color: #1d4ed8;
}

.employee-layout__content {
  padding: 8px 0 32px;
}

@media (max-width: 640px) {
  .employee-layout {
    padding: 16px;
  }

  .employee-layout__header,
  .employee-layout__search-row {
    align-items: stretch;
    flex-direction: column;
  }

  .employee-layout__user {
    justify-content: space-between;
  }

  .employee-layout__nav {
    grid-template-columns: 1fr;
  }
}
</style>
