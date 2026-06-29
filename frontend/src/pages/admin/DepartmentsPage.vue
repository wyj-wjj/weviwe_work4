<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  createAdminDepartment,
  disableAdminDepartment,
  enableAdminDepartment,
  listAdminDepartments,
  updateAdminDepartment,
  type Department,
} from '../../api/admin-departments'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { formatDateTime } from '../../utils/format'

const items = ref<Department[]>([])
const state = ref<'loading' | 'ready' | 'service'>('loading')
const showEditor = ref(false)
const editingId = ref<number | null>(null)
const message = ref('')
const error = ref('')
const form = reactive({
  name: '',
  code: '',
})

async function loadDepartments() {
  if (items.value.length === 0) {
    state.value = 'loading'
  }
  try {
    const response = await listAdminDepartments(true)
    items.value = response.items
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

function resetEditor() {
  editingId.value = null
  form.name = ''
  form.code = ''
  error.value = ''
}

function startCreate() {
  resetEditor()
  showEditor.value = true
}

function startEdit(department: Department) {
  editingId.value = department.id
  form.name = department.name
  form.code = department.code
  error.value = ''
  showEditor.value = true
}

async function saveDepartment() {
  if (!form.name || !form.code) {
    error.value = '请填写部门名称和部门编码'
    return
  }
  try {
    if (editingId.value) {
      await updateAdminDepartment(editingId.value, { name: form.name, code: form.code })
    } else {
      await createAdminDepartment({ name: form.name, code: form.code })
    }
    message.value = '部门已保存'
    showEditor.value = false
    resetEditor()
    await loadDepartments()
  } catch {
    error.value = '部门保存失败，请检查编码是否重复'
  }
}

async function disableDepartment(department: Department) {
  if (!window.confirm(`确认停用部门“${department.name}”吗？已有内容不会被删除。`)) {
    return
  }
  await disableAdminDepartment(department.id)
  message.value = '部门已停用'
  await loadDepartments()
}

async function enableDepartment(department: Department) {
  await enableAdminDepartment(department.id)
  message.value = '部门已启用'
  await loadDepartments()
}

onMounted(loadDepartments)
</script>

<template>
  <AdminLayout>
    <section class="admin-page">
      <header class="admin-page__title">
        <div>
          <h2>部门管理</h2>
          <p>维护员工归属部门和部门限定内容的可见范围。</p>
        </div>
        <button class="admin-button admin-button--primary" type="button" @click="startCreate">
          新建部门
        </button>
      </header>

      <p v-if="message" class="admin-notice">{{ message }}</p>

      <form v-if="showEditor" class="admin-form admin-panel" @submit.prevent="saveDepartment">
        <label>
          <span>部门名称</span>
          <input v-model.trim="form.name" type="text" />
        </label>
        <label>
          <span>部门编码</span>
          <input v-model.trim="form.code" type="text" />
        </label>
        <p v-if="error" class="admin-error">{{ error }}</p>
        <div class="admin-form__actions">
          <button class="admin-button admin-button--primary" type="submit">保存部门</button>
          <button class="admin-button" type="button" @click="showEditor = false">取消</button>
        </div>
      </form>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="items.length === 0" state="empty" message="暂无部门" />

      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>部门名称</th>
              <th>部门编码</th>
              <th>状态</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="department in items" :key="department.id">
              <td>{{ department.name }}</td>
              <td>{{ department.code }}</td>
              <td>{{ department.is_active ? '启用' : '停用' }}</td>
              <td>{{ formatDateTime(department.updated_at) }}</td>
              <td>
                <div class="admin-actions">
                  <button type="button" @click="startEdit(department)">编辑</button>
                  <button
                    v-if="department.is_active"
                    type="button"
                    @click="disableDepartment(department)"
                  >
                    停用
                  </button>
                  <button v-else type="button" @click="enableDepartment(department)">启用</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </AdminLayout>
</template>
