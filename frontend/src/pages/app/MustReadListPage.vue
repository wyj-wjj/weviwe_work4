<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { listMustReads, type MustReadItem } from '../../api/content'
import AppState from '../../components/AppState.vue'
import EmployeeLayout from '../../components/EmployeeLayout.vue'
import { formatDateTime, permissionLabel, scopeLabel, updateLevelLabel } from '../../utils/format'

const items = ref<MustReadItem[]>([])
const state = ref<'loading' | 'ready' | 'service'>('loading')

onMounted(async () => {
  state.value = 'loading'
  try {
    const response = await listMustReads()
    items.value = response.items
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
})
</script>

<template>
  <EmployeeLayout>
    <section class="page-section">
      <header class="page-section__header">
        <h2>最新必读</h2>
      </header>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState
        v-else-if="items.length === 0"
        state="empty"
        message="暂无可查看的最新必读"
      />

      <div v-else class="content-list">
        <RouterLink
          v-for="item in items"
          :key="item.id"
          class="content-list__item"
          :to="`/app/must-reads/${item.id}`"
        >
          <strong>{{ item.title }}</strong>
          <span>发布时间：{{ formatDateTime(item.published_at) }}</span>
          <span>生效时间：{{ formatDateTime(item.effective_at) }}</span>
          <span>更新级别：{{ updateLevelLabel(item.update_level) }}</span>
          <span>可见范围：{{ scopeLabel(item.scope_type) }}</span>
          <em>{{ permissionLabel(item.permission_level) }}</em>
        </RouterLink>
      </div>
    </section>
  </EmployeeLayout>
</template>

<style scoped>
.page-section__header h2 {
  font-size: 22px;
  margin: 0 0 16px;
}

.content-list {
  display: grid;
  gap: 12px;
}

.content-list__item {
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  color: #1f2933;
  display: grid;
  gap: 8px;
  padding: 16px;
  text-decoration: none;
}

.content-list__item strong {
  font-size: 17px;
}

.content-list__item span,
.content-list__item em {
  color: #52606d;
  font-style: normal;
}
</style>
