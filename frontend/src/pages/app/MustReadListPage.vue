<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { listMustReads, type MustReadItem } from '../../api/content'
import AppState from '../../components/AppState.vue'
import EmployeeLayout from '../../components/EmployeeLayout.vue'
import { formatDateTime, permissionLabel, scopeLabel, updateLevelLabel } from '../../utils/format'

const items = ref<MustReadItem[]>([])
const state = ref<'loading' | 'ready' | 'service'>('loading')
const selectedCategory = ref('')
const selectedScope = ref('')
const page = ref(1)
const pageSize = 10

const categories = computed(() => {
  const merged = new Set<string>()
  for (const item of items.value) {
    const category = item.category?.trim()
    if (category) {
      merged.add(category)
    }
  }
  return Array.from(merged)
})

const filteredItems = computed(() =>
  items.value.filter((item) => {
    if (selectedCategory.value && item.category !== selectedCategory.value) {
      return false
    }
    if (selectedScope.value && item.scope_type !== selectedScope.value) {
      return false
    }
    return true
  }),
)

const totalPages = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / pageSize)))
const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredItems.value.slice(start, start + pageSize)
})

function resetPage() {
  page.value = 1
}

function changePage(nextPage: number) {
  page.value = nextPage
}

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
        <div class="must-read-filters">
          <label>
            <span>分类</span>
            <select v-model="selectedCategory" @change="resetPage">
              <option value="">全部</option>
              <option v-for="category in categories" :key="category" :value="category">
                {{ category }}
              </option>
            </select>
          </label>
          <label>
            <span>可见范围</span>
            <select v-model="selectedScope" @change="resetPage">
              <option value="">全部</option>
              <option value="global">全公司通用</option>
              <option value="department">本部门</option>
            </select>
          </label>
        </div>
      </header>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState
        v-else-if="filteredItems.length === 0"
        state="empty"
        message="暂无可查看的最新必读"
      />

      <div v-else class="content-list">
        <RouterLink
          v-for="item in pagedItems"
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

      <footer v-if="state === 'ready' && filteredItems.length > 0" class="content-pagination">
        <button type="button" :disabled="page <= 1" @click="changePage(page - 1)">
          上一页
        </button>
        <span>第 {{ page }} / {{ totalPages }} 页，共 {{ filteredItems.length }} 条</span>
        <button type="button" :disabled="page >= totalPages" @click="changePage(page + 1)">
          下一页
        </button>
      </footer>
    </section>
  </EmployeeLayout>
</template>

<style scoped>
.page-section__header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.page-section__header h2 {
  font-size: 22px;
  margin: 0;
}

.must-read-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.must-read-filters label {
  display: grid;
  gap: 6px;
}

.must-read-filters select {
  border: 1px solid #bcccdc;
  border-radius: 6px;
  font: inherit;
  min-height: 36px;
  padding: 0 10px;
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

.content-pagination {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 14px;
}

.content-pagination button {
  border: 1px solid #bcccdc;
  border-radius: 6px;
  background: #ffffff;
  cursor: pointer;
  font: inherit;
  min-height: 36px;
  padding: 0 12px;
}

.content-pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
