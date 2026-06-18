<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getMustRead, type MustReadItem } from '../../api/content'
import AppState from '../../components/AppState.vue'
import EmployeeLayout from '../../components/EmployeeLayout.vue'
import { formatDateTime, permissionLabel } from '../../utils/format'

const route = useRoute()
const item = ref<MustReadItem | null>(null)
const state = ref<'loading' | 'ready' | 'permission' | 'service'>('loading')

onMounted(async () => {
  item.value = null
  state.value = 'loading'
  try {
    item.value = await getMustRead(String(route.params.contentId))
    state.value = 'ready'
  } catch (error) {
    const apiError = error as { status?: number }
    state.value = apiError.status === 403 ? 'permission' : 'service'
  }
})
</script>

<template>
  <EmployeeLayout>
    <AppState v-if="state === 'loading'" state="loading" />
    <AppState v-else-if="state === 'permission'" state="permission" />
    <AppState v-else-if="state === 'service'" state="service" />

    <article v-else-if="item" class="detail-page">
      <header>
        <h2>{{ item.title }}</h2>
        <p>
          <span>发布时间：{{ formatDateTime(item.published_at) }}</span>
          <span>生效时间：{{ formatDateTime(item.effective_at) }}</span>
          <strong>{{ permissionLabel(item.permission_level) }}</strong>
        </p>
      </header>

      <section>
        <h3>更新正文</h3>
        <p>{{ item.update_body }}</p>
      </section>

      <section>
        <h3>调整要点</h3>
        <ul>
          <li v-for="point in item.adjustment_points" :key="point">{{ point }}</li>
        </ul>
      </section>
    </article>
  </EmployeeLayout>
</template>

<style scoped>
.detail-page {
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  display: grid;
  gap: 20px;
  padding: 20px;
}

.detail-page h2 {
  font-size: 24px;
  margin: 0 0 12px;
}

.detail-page h3 {
  font-size: 17px;
  margin: 0 0 8px;
}

.detail-page p {
  line-height: 1.7;
  margin: 0;
}

.detail-page header p {
  color: #52606d;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.detail-page header strong {
  color: #1d4ed8;
}
</style>
