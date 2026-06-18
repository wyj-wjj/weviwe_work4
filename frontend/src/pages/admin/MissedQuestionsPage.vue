<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  listAdminMissedQuestions,
  markAdminMissedQuestionHandled,
  type AdminMissedQuestion,
} from '../../api/admin-missed-questions'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { formatDateTime, permissionLabel } from '../../utils/format'

const items = ref<AdminMissedQuestion[]>([])
const status = ref('')
const page = ref(1)
const state = ref<'loading' | 'ready' | 'service'>('loading')
const message = ref('')

const accountLabels: Record<string, string> = {
  admin: '管理员',
  full_user: '完整权限员工',
  general_user: '通用权限员工',
}

async function loadQuestions() {
  state.value = 'loading'
  try {
    const response = await listAdminMissedQuestions(status.value, page.value)
    items.value = response.items
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

async function applyFilter() {
  page.value = 1
  await loadQuestions()
}

async function markHandled(item: AdminMissedQuestion) {
  try {
    const updated = await markAdminMissedQuestionHandled(item.id)
    Object.assign(item, updated)
    message.value = '问题已标记为已处理'
  } catch {
    message.value = '状态更新失败，请稍后重试'
  }
}

onMounted(loadQuestions)
</script>

<template>
  <AdminLayout>
    <section class="admin-page">
      <header class="admin-page__title">
        <div>
          <h2>未命中问题</h2>
          <p>查看员工未获得有效标准口径的问题，并跟进内容补充。</p>
        </div>
      </header>

      <form class="admin-filters admin-filters--compact" @submit.prevent="applyFilter">
        <label>
          <span>处理状态</span>
          <select v-model="status">
            <option value="">全部</option>
            <option value="new">新建</option>
            <option value="handled">已处理</option>
          </select>
        </label>
        <button class="admin-button" type="submit">筛选</button>
      </form>

      <p v-if="message" class="admin-notice">{{ message }}</p>
      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="items.length === 0" state="empty" message="暂无未处理问题" />
      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>问题文本</th>
              <th>提问时间</th>
              <th>用户</th>
              <th>权限快照</th>
              <th>状态</th>
              <th>处理时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>{{ item.question }}</td>
              <td>{{ formatDateTime(item.asked_at) }}</td>
              <td>{{ item.username || `用户 ${item.user_id || '-'}` }}</td>
              <td>
                {{ accountLabels[item.account_type] }} / {{ permissionLabel(item.content_level) }}
              </td>
              <td>{{ item.status === 'handled' ? '已处理' : '新建' }}</td>
              <td>{{ formatDateTime(item.handled_at) }}</td>
              <td>
                <button
                  v-if="item.status === 'new'"
                  type="button"
                  @click="markHandled(item)"
                >
                  标记已处理
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </AdminLayout>
</template>
