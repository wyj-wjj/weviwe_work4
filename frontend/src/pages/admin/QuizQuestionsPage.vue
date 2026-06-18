<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  createAdminQuizQuestion,
  listAdminQuizQuestions,
  setAdminQuizQuestionStatus,
  updateAdminQuizQuestion,
  type AdminQuizQuestion,
  type AdminQuizPayload,
} from '../../api/admin-quiz'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { formatDateTime, permissionLabel } from '../../utils/format'

const items = ref<AdminQuizQuestion[]>([])
const state = ref<'loading' | 'ready' | 'service'>('loading')
const editingId = ref<number | null>(null)
const showEditor = ref(false)
const error = ref('')
const message = ref('')

const form = reactive({
  question: '',
  options: '',
  answer: '',
  explanation: '',
  related_content_id: '',
  permission_level: 'general',
  status: 'enabled',
})

function optionText(option: string | { label?: string; value?: string }) {
  return typeof option === 'string' ? option : (option.value ?? option.label ?? '')
}

async function loadQuestions() {
  if (items.value.length === 0) {
    state.value = 'loading'
  }
  try {
    const response = await listAdminQuizQuestions()
    items.value = response.items
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

function resetEditor() {
  editingId.value = null
  form.question = ''
  form.options = ''
  form.answer = ''
  form.explanation = ''
  form.related_content_id = ''
  form.permission_level = 'general'
  form.status = 'enabled'
  error.value = ''
}

function startCreate() {
  resetEditor()
  showEditor.value = true
}

function startEdit(item: AdminQuizQuestion) {
  editingId.value = item.id
  form.question = item.question
  form.options = item.options.map(optionText).join('\n')
  form.answer = item.answer
  form.explanation = item.explanation || ''
  form.related_content_id = item.related_content_id ? String(item.related_content_id) : ''
  form.permission_level = item.permission_level
  form.status = item.status
  error.value = ''
  showEditor.value = true
}

function buildPayload(): AdminQuizPayload {
  return {
    question: form.question,
    options: form.options
      .split('\n')
      .map((option) => option.trim())
      .filter(Boolean),
    answer: form.answer,
    explanation: form.explanation || null,
    related_content_id: form.related_content_id ? Number(form.related_content_id) : null,
    permission_level: form.permission_level as AdminQuizPayload['permission_level'],
    status: form.status as AdminQuizPayload['status'],
  }
}

async function saveQuestion() {
  const payload = buildPayload()
  if (!payload.question || payload.options.length < 2 || !payload.answer || !payload.explanation) {
    error.value = '请完整填写题干、至少两个选项、正确答案和解析'
    return
  }
  try {
    if (editingId.value) {
      await updateAdminQuizQuestion(editingId.value, payload)
    } else {
      await createAdminQuizQuestion(payload)
    }
    message.value = '测验题已保存'
    showEditor.value = false
    resetEditor()
    await loadQuestions()
  } catch {
    error.value = '测验题保存失败，请稍后重试'
  }
}

async function setStatus(item: AdminQuizQuestion, status: AdminQuizQuestion['status']) {
  try {
    await setAdminQuizQuestionStatus(item.id, status)
    await loadQuestions()
    const refreshed = items.value.find((candidate) => candidate.id === item.id)
    if (refreshed) {
      refreshed.status = status
    }
    message.value = status === 'enabled' ? '测验题已启用' : '测验题已禁用'
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
          <h2>测验题管理</h2>
          <p>维护员工巩固测试题，题目仍由后端按权限过滤。</p>
        </div>
        <button class="admin-button admin-button--primary" type="button" @click="startCreate">
          新建测验题
        </button>
      </header>

      <p v-if="message" class="admin-notice">{{ message }}</p>

      <form v-if="showEditor" class="admin-form admin-panel" @submit.prevent="saveQuestion">
        <label class="admin-form__wide">
          <span>题干</span>
          <textarea v-model.trim="form.question" rows="3" />
        </label>
        <label class="admin-form__wide">
          <span>选项（每行一个）</span>
          <textarea v-model="form.options" rows="4" />
        </label>
        <label>
          <span>正确答案</span>
          <input v-model.trim="form.answer" type="text" />
        </label>
        <label class="admin-form__wide">
          <span>解析</span>
          <textarea v-model.trim="form.explanation" rows="3" />
        </label>
        <label>
          <span>关联话术 ID</span>
          <input v-model="form.related_content_id" type="number" min="1" />
        </label>
        <label>
          <span>权限级别</span>
          <select v-model="form.permission_level">
            <option value="general">通用级</option>
            <option value="full">全量级</option>
          </select>
        </label>
        <label>
          <span>状态</span>
          <select v-model="form.status">
            <option value="enabled">启用</option>
            <option value="disabled">禁用</option>
          </select>
        </label>
        <p v-if="error" class="admin-error">{{ error }}</p>
        <div class="admin-form__actions">
          <button class="admin-button admin-button--primary" type="submit">保存测验题</button>
          <button class="admin-button" type="button" @click="showEditor = false">取消</button>
        </div>
      </form>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="items.length === 0" state="empty" message="暂无测验题" />
      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>题干</th>
              <th>权限</th>
              <th>关联话术</th>
              <th>状态</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>{{ item.question }}</td>
              <td>{{ permissionLabel(item.permission_level) }}</td>
              <td>{{ item.related_content_title || item.related_content_id || '-' }}</td>
              <td>{{ item.status === 'enabled' ? '启用' : '禁用' }}</td>
              <td>{{ formatDateTime(item.updated_at) }}</td>
              <td>
                <div class="admin-actions">
                  <button type="button" @click="startEdit(item)">编辑</button>
                  <button
                    v-if="item.status === 'enabled'"
                    type="button"
                    @click="setStatus(item, 'disabled')"
                  >
                    禁用
                  </button>
                  <button v-else type="button" @click="setStatus(item, 'enabled')">
                    启用
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </AdminLayout>
</template>
