<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  createAdminContent,
  getAdminContent,
  updateAdminContent,
  type AdminContentPayload,
} from '../../api/admin-content'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'

const route = useRoute()
const router = useRouter()
const contentId = computed(() => Number(route.params.contentId || 0))
const isEditing = computed(() => contentId.value > 0)
const state = ref<'ready' | 'loading' | 'service'>('ready')
const error = ref('')
const isSaving = ref(false)

const form = reactive({
  title: '',
  content_type: '',
  category: '',
  permission_level: '',
  summary: '',
  body: '',
  scene: '',
  recommended_speech: '',
  forbidden_speech: '',
  notes: '',
  update_body: '',
  adjustment_points: '',
})

function applyContent(content: Awaited<ReturnType<typeof getAdminContent>>) {
  const payload = content.structured_payload || {}
  form.title = content.title
  form.content_type = content.content_type
  form.category = content.category || ''
  form.permission_level = content.permission_level
  form.summary = content.summary || ''
  form.body = content.body
  form.scene = String(payload.scene || '')
  form.recommended_speech = String(payload.recommended_speech || '')
  form.forbidden_speech = String(payload.forbidden_speech || '')
  form.notes = String(payload.notes || '')
  form.update_body = String(payload.update_body || content.body)
  form.adjustment_points = Array.isArray(payload.adjustment_points)
    ? payload.adjustment_points.join('\n')
    : ''
}

async function loadContent() {
  if (!isEditing.value) {
    return
  }
  state.value = 'loading'
  try {
    applyContent(await getAdminContent(contentId.value))
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

function lines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function buildPayload(): AdminContentPayload {
  let structuredPayload: Record<string, unknown> = {
    points: lines(form.summary),
  }
  if (form.content_type === 'standard_script') {
    structuredPayload = {
      scene: form.scene,
      recommended_speech: form.recommended_speech,
      forbidden_speech: form.forbidden_speech,
      notes: form.notes,
    }
  } else if (form.content_type === 'must_read') {
    structuredPayload = {
      update_body: form.update_body,
      adjustment_points: lines(form.adjustment_points),
    }
  }
  return {
    title: form.title,
    content_type: form.content_type as AdminContentPayload['content_type'],
    category: form.category,
    permission_level: form.permission_level as AdminContentPayload['permission_level'],
    summary: form.summary,
    body: form.body,
    structured_payload: structuredPayload,
  }
}

function isValid() {
  if (
    !form.title ||
    !form.content_type ||
    !form.category ||
    !form.permission_level ||
    !form.summary ||
    !form.body
  ) {
    return false
  }
  if (form.content_type === 'standard_script') {
    return Boolean(form.scene && form.recommended_speech)
  }
  if (form.content_type === 'must_read') {
    return Boolean(form.update_body && lines(form.adjustment_points).length)
  }
  return true
}

async function saveDraft() {
  error.value = ''
  if (!isValid()) {
    error.value = '请完整填写必填字段'
    return
  }
  isSaving.value = true
  try {
    const payload = buildPayload()
    if (isEditing.value) {
      const { content_type: _contentType, ...updatePayload } = payload
      await updateAdminContent(contentId.value, updatePayload)
    } else {
      await createAdminContent(payload)
    }
    await router.push('/admin/contents')
  } catch {
    error.value = '草稿保存失败，请稍后重试'
  } finally {
    isSaving.value = false
  }
}

onMounted(loadContent)
</script>

<template>
  <AdminLayout>
    <section class="admin-page">
      <header class="admin-page__title">
        <div>
          <h2>{{ isEditing ? '编辑内容' : '新建内容' }}</h2>
          <p>保存为草稿后，可在内容列表中确认并发布。</p>
        </div>
      </header>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <form v-else class="admin-form" @submit.prevent="saveDraft">
        <label>
          <span>标题</span>
          <input v-model.trim="form.title" type="text" />
        </label>
        <label>
          <span>内容类型</span>
          <select v-model="form.content_type" :disabled="isEditing">
            <option value="">请选择</option>
            <option value="base_script">核心基础话术</option>
            <option value="standard_script">标准化话术</option>
            <option value="must_read">最新必读</option>
          </select>
        </label>
        <label>
          <span>分类</span>
          <input v-model.trim="form.category" type="text" />
        </label>
        <label>
          <span>权限级别</span>
          <select v-model="form.permission_level">
            <option value="">请选择</option>
            <option value="general">通用级</option>
            <option value="full">全量级</option>
          </select>
        </label>
        <label class="admin-form__wide">
          <span>摘要</span>
          <textarea v-model.trim="form.summary" rows="3" />
        </label>
        <label class="admin-form__wide">
          <span>正文</span>
          <textarea v-model.trim="form.body" rows="8" />
        </label>

        <template v-if="form.content_type === 'standard_script'">
          <label>
            <span>场景</span>
            <input v-model.trim="form.scene" type="text" />
          </label>
          <label class="admin-form__wide">
            <span>推荐说法</span>
            <textarea v-model.trim="form.recommended_speech" rows="4" />
          </label>
          <label class="admin-form__wide">
            <span>禁用说法</span>
            <textarea v-model.trim="form.forbidden_speech" rows="3" />
          </label>
          <label class="admin-form__wide">
            <span>注意事项</span>
            <textarea v-model.trim="form.notes" rows="3" />
          </label>
        </template>

        <template v-if="form.content_type === 'must_read'">
          <label class="admin-form__wide">
            <span>更新正文</span>
            <textarea v-model.trim="form.update_body" rows="5" />
          </label>
          <label class="admin-form__wide">
            <span>调整要点</span>
            <textarea
              v-model.trim="form.adjustment_points"
              rows="4"
              placeholder="每行一个调整要点"
            />
          </label>
        </template>

        <p v-if="error" class="admin-error">{{ error }}</p>
        <div class="admin-form__actions">
          <button class="admin-button admin-button--primary" type="submit" :disabled="isSaving">
            {{ isSaving ? '保存中' : '保存草稿' }}
          </button>
          <button class="admin-button" type="button" @click="router.push('/admin/contents')">
            取消
          </button>
        </div>
      </form>
    </section>
  </AdminLayout>
</template>
