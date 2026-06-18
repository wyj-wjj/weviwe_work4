<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  listAdminContentVersions,
  type AdminContentVersion,
} from '../../api/admin-content'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { formatDateTime, permissionLabel } from '../../utils/format'

const route = useRoute()
const versions = ref<AdminContentVersion[]>([])
const state = ref<'loading' | 'ready' | 'service'>('loading')

async function loadVersions() {
  try {
    const response = await listAdminContentVersions(Number(route.params.contentId))
    versions.value = response.items
    state.value = 'ready'
  } catch {
    state.value = 'service'
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
          <p v-if="version.summary">摘要：{{ version.summary }}</p>
          <pre>{{ version.body }}</pre>
        </article>
      </div>
    </section>
  </AdminLayout>
</template>
