<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { listAdminDepartments, type Department } from '../../api/admin-departments'
import {
  createAdminUser,
  disableAdminUser,
  enableAdminUser,
  listAdminUsers,
  resetAdminUserPassword,
  updateAdminUser,
  type AdminUser,
  type AdminUserCreatePayload,
} from '../../api/admin-users'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { useAuthStore } from '../../stores/auth'
import { formatDateTime, permissionLabel } from '../../utils/format'

const auth = useAuthStore()
const items = ref<AdminUser[]>([])
const departments = ref<Department[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const state = ref<'loading' | 'ready' | 'service'>('loading')
const showEditor = ref(false)
const editingId = ref<number | null>(null)
const resetUserId = ref<number | null>(null)
const resetPassword = ref('')
const resetError = ref('')
const error = ref('')
const message = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const form = reactive({
  username: '',
  password: '',
  display_name: '',
  account_type: 'general_user',
  content_level: 'general',
  department_id: null as number | null,
  is_active: true,
})

const accountLabels: Record<string, string> = {
  admin: '管理员',
  full_user: '完整权限员工',
  general_user: '通用权限员工',
}

async function loadUsers() {
  if (items.value.length === 0) {
    state.value = 'loading'
  }
  try {
    const response = await listAdminUsers(page.value, pageSize)
    items.value = response.items
    total.value = response.total
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

async function changePage(nextPage: number) {
  page.value = nextPage
  await loadUsers()
}

async function loadDepartments() {
  const response = await listAdminDepartments(false)
  departments.value = response.items
}

function resetEditor() {
  editingId.value = null
  form.username = ''
  form.password = ''
  form.display_name = ''
  form.account_type = 'general_user'
  form.content_level = 'general'
  form.department_id = null
  form.is_active = true
  error.value = ''
}

function startCreate() {
  resetEditor()
  showEditor.value = true
}

function startEdit(user: AdminUser) {
  editingId.value = user.id
  form.username = user.username
  form.password = ''
  form.display_name = user.display_name
  form.account_type = user.account_type
  form.content_level = user.content_level
  form.department_id = user.department_id
  form.is_active = user.is_active
  error.value = ''
  showEditor.value = true
}

function syncContentLevel() {
  if (form.account_type === 'general_user') {
    form.content_level = 'general'
  } else if (form.account_type === 'full_user') {
    form.content_level = 'full'
  }
}

async function saveUser() {
  if (
    !form.username ||
    !form.display_name ||
    !form.account_type ||
    !form.content_level ||
    (!editingId.value && form.password.length < 8)
  ) {
    error.value = '请完整填写账号信息，新账号密码至少 8 位'
    return
  }
  try {
    if (editingId.value) {
      const payload = {
        display_name: form.display_name,
        account_type: form.account_type as AdminUser['account_type'],
        content_level: form.content_level as AdminUser['content_level'],
        is_active: form.is_active,
      } as Parameters<typeof updateAdminUser>[1]
      if (form.department_id !== null) {
        payload.department_id = form.department_id
      }
      await updateAdminUser(editingId.value, payload)
    } else {
      const payload: AdminUserCreatePayload = {
        username: form.username,
        password: form.password,
        display_name: form.display_name,
        account_type: form.account_type as AdminUser['account_type'],
        content_level: form.content_level as AdminUser['content_level'],
      }
      if (form.department_id !== null) {
        payload.department_id = form.department_id
      }
      await createAdminUser(payload)
    }
    message.value = '账号已保存'
    showEditor.value = false
    resetEditor()
    await loadUsers()
  } catch {
    error.value = '账号保存失败，请检查用户名是否重复或部门是否可用'
  }
}

function startReset(user: AdminUser) {
  resetUserId.value = user.id
  resetPassword.value = ''
  resetError.value = ''
  error.value = ''
  message.value = ''
}

function cancelReset() {
  resetUserId.value = null
  resetPassword.value = ''
  resetError.value = ''
}

async function confirmReset() {
  resetError.value = ''
  if (!resetUserId.value) {
    return
  }
  if (!resetPassword.value) {
    resetError.value = '请输入新密码'
    return
  }
  if (resetPassword.value.length < 8) {
    resetError.value = '新密码至少 8 位'
    return
  }
  if (!window.confirm('确认重置该账号密码吗？')) {
    return
  }
  try {
    await resetAdminUserPassword(resetUserId.value, resetPassword.value)
    resetUserId.value = null
    resetPassword.value = ''
    resetError.value = ''
    message.value = '密码已重置，请安全通知该用户；此提示不会再次展示。'
  } catch {
    resetError.value = '新密码至少 8 位'
  }
}

async function disable(user: AdminUser) {
  if (!window.confirm(`确认禁用账号“${user.username}”吗？`)) {
    return
  }
  try {
    await disableAdminUser(user.id)
    message.value = '账号已禁用'
    await loadUsers()
  } catch {
    message.value = '账号禁用失败，请稍后重试'
  }
}

async function enable(user: AdminUser) {
  if (!window.confirm(`确认启用账号“${user.username}”吗？`)) {
    return
  }
  try {
    await enableAdminUser(user.id)
    message.value = '账号已启用'
    await loadUsers()
  } catch {
    message.value = '账号启用失败，请稍后重试'
  }
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadDepartments()])
})
</script>

<template>
  <AdminLayout>
    <section class="admin-page">
      <header class="admin-page__title">
        <div>
          <h2>账号管理</h2>
          <p>新增、编辑、重置密码或禁用员工账号。</p>
        </div>
        <button class="admin-button admin-button--primary" type="button" @click="startCreate">
          新增账号
        </button>
      </header>

      <p v-if="message" class="admin-notice">{{ message }}</p>

      <form v-if="showEditor" class="admin-form admin-panel" @submit.prevent="saveUser">
        <label>
          <span>用户名</span>
          <input v-model.trim="form.username" type="text" :disabled="Boolean(editingId)" />
        </label>
        <label v-if="!editingId">
          <span>初始密码</span>
          <input v-model="form.password" type="password" />
        </label>
        <label>
          <span>展示名</span>
          <input v-model.trim="form.display_name" type="text" />
        </label>
        <label>
          <span>账号类型</span>
          <select v-model="form.account_type" @change="syncContentLevel">
            <option value="general_user">通用权限员工</option>
            <option value="full_user">完整权限员工</option>
          </select>
        </label>
        <label>
          <span>内容权限级别</span>
          <select v-model="form.content_level">
            <option value="general">通用级</option>
            <option value="full">全量级</option>
          </select>
        </label>
        <label>
          <span>归属部门</span>
          <select v-model.number="form.department_id">
            <option :value="null">未分配（仅可看全公司通用）</option>
            <option v-for="department in departments" :key="department.id" :value="department.id">
              {{ department.name }}
            </option>
          </select>
        </label>
        <label v-if="editingId" class="admin-checkbox">
          <input v-model="form.is_active" type="checkbox" />
          <span>账号启用</span>
        </label>
        <p v-if="error" class="admin-error">{{ error }}</p>
        <div class="admin-form__actions">
          <button class="admin-button admin-button--primary" type="submit">保存账号</button>
          <button class="admin-button" type="button" @click="showEditor = false">取消</button>
        </div>
      </form>

      <form v-if="resetUserId" class="admin-reset-panel" @submit.prevent="confirmReset">
        <label>
          <span>新密码</span>
          <input
            v-model="resetPassword"
            type="password"
            minlength="8"
            maxlength="128"
            autocomplete="new-password"
          />
        </label>
        <p v-if="resetError" class="admin-error">{{ resetError }}</p>
        <button class="admin-button admin-button--primary" type="submit">确认重置</button>
        <button class="admin-button" type="button" @click="cancelReset">取消</button>
      </form>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="items.length === 0" state="empty" message="暂无账号" />
      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>展示名</th>
              <th>账号类型</th>
              <th>内容权限</th>
              <th>归属部门</th>
              <th>状态</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in items" :key="user.id">
              <td>{{ user.username }}</td>
              <td>{{ user.display_name }}</td>
              <td>{{ accountLabels[user.account_type] }}</td>
              <td>{{ permissionLabel(user.content_level) }}</td>
              <td>{{ user.department_name || '未分配' }}</td>
              <td>{{ user.is_active ? '启用' : '禁用' }}</td>
              <td>{{ formatDateTime(user.updated_at) }}</td>
              <td>
                <div v-if="user.account_type !== 'admin'" class="admin-actions">
                  <button type="button" @click="startEdit(user)">编辑</button>
                  <button type="button" @click="startReset(user)">重置密码</button>
                  <button v-if="user.is_active && user.id !== auth.user?.id" type="button" @click="disable(user)">
                    禁用账号
                  </button>
                  <button v-else-if="!user.is_active" type="button" @click="enable(user)">
                    启用账号
                  </button>
                </div>
                <span v-else>系统管理员只读</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer v-if="state === 'ready' && total > 0" class="admin-pagination">
        <button
          class="admin-button"
          type="button"
          :disabled="page <= 1"
          @click="changePage(page - 1)"
        >
          上一页
        </button>
        <span>第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
        <button
          class="admin-button"
          type="button"
          :disabled="page >= totalPages"
          @click="changePage(page + 1)"
        >
          下一页
        </button>
      </footer>
    </section>
  </AdminLayout>
</template>
