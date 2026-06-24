<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  listAdminContentVersions,
  type AdminContentVersion,
} from '../../api/admin-content'
import { generateAdminQuizForContentVersion } from '../../api/admin-quiz'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { formatDateTime, permissionLabel } from '../../utils/format'

const route = useRoute()
const versions = ref<AdminContentVersion[]>([])
const state = ref<'loading' | 'ready' | 'service'>('loading')
const message = ref('')
const generationError = ref('')
const generatingVersionId = ref<number | null>(null)

const updateLevelLabels: Record<AdminContentVersion['update_level'], string> = {
  minor: '小更新',
  medium: '中更新',
  major: '大更新',
}

const quizActionLabels: Record<AdminContentVersion['quiz_action'], string> = {
  none: '不影响题库',
  review_related: '复核关联旧题',
  generate_pack: '建议生成专题候选题',
}

async function loadVersions() {
  try {
    const response = await listAdminContentVersions(Number(route.params.contentId))
    versions.value = response.items
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

async function generateQuizCandidates(version: AdminContentVersion) {
  message.value = ''
  generationError.value = ''
  generatingVersionId.value = version.id
  try {
    const batch = await generateAdminQuizForContentVersion(
      Number(route.params.contentId),
      version.id,
      { create_quiz_set: version.update_level === 'major' },
    )
    if (batch.status === 'failed') {
      generationError.value = `候选题生成失败：${batch.error_message || '请稍后重试'}`
    } else {
      message.value = `已生成 ${batch.generated_count} 道候选题，批次 ID：${batch.id}`
    }
  } catch {
    generationError.value = '候选题生成失败，请稍后重试'
  } finally {
    generatingVersionId.value = null
  }
}

onMounted(loadVersions)
</script>

<template>
  <AdminLayout>
    <section class="admin-page">
      <header class="admin-page__title">
        <div>
          <h2>历史版本</h2>
          <p>历史快照仅供管理员追溯，不参与员工端展示和 AI 检索。</p>
        </div>
      </header>

      <p v-if="message" class="admin-notice">{{ message }}</p>
      <p v-if="generationError" class="admin-error">{{ generationError }}</p>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="versions.length === 0" state="empty" message="暂无历史版本" />
      <div v-else class="admin-card-list">
        <article v-for="version in versions" :key="version.id" class="admin-card">
          <header>
            <div>
              <strong>版本 {{ version.version_no }}</strong>
              <h3>{{ version.title }}</h3>
            </div>
            <span class="status-tag">{{ permissionLabel(version.permission_level) }}</span>
          </header>
          <p>发布时间：{{ formatDateTime(version.published_at) }}</p>
          <p>发布人：{{ version.created_by_name || `用户 ${version.created_by}` }}</p>
          <p>更新级别：{{ updateLevelLabels[version.update_level] }}</p>
          <p>题库动作：{{ quizActionLabels[version.quiz_action] }}</p>
          <button
            v-if="version.quiz_action !== 'none'"
            class="admin-button"
            type="button"
            :disabled="generatingVersionId === version.id"
            @click="generateQuizCandidates(version)"
          >
            {{ generatingVersionId === version.id ? '生成中...' : '生成候选题' }}
          </button>
          <p v-if="version.change_summary">变更摘要：{{ version.change_summary }}</p>
          <p v-if="version.summary">摘要：{{ version.summary }}</p>
          <pre>{{ version.body }}</pre>
        </article>
      </div>
    </section>
  </AdminLayout>
</template>
