<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { listScripts, type BaseScriptItem, type StandardScriptItem } from '../../api/content'
import AppState from '../../components/AppState.vue'
import EmployeeLayout from '../../components/EmployeeLayout.vue'
import { formatDateTime, permissionLabel, scopeLabel, updateLevelLabel } from '../../utils/format'

const baseScripts = ref<BaseScriptItem[]>([])
const standardScripts = ref<StandardScriptItem[]>([])
const categories = ref<string[]>([])
const selectedCategory = ref('')
const state = ref<'loading' | 'ready' | 'service'>('loading')

const hasContent = computed(() => baseScripts.value.length > 0 || standardScripts.value.length > 0)

function rememberCategories(items: Array<BaseScriptItem | StandardScriptItem>) {
  const merged = new Set(categories.value)
  for (const item of items) {
    if (item.category) {
      merged.add(item.category)
    }
  }
  categories.value = Array.from(merged)
}

async function loadScripts() {
  state.value = 'loading'
  try {
    const response = await listScripts({ category: selectedCategory.value || undefined })
    baseScripts.value = response.base_scripts
    standardScripts.value = response.standard_scripts
    rememberCategories([...response.base_scripts, ...response.standard_scripts])
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

onMounted(loadScripts)
</script>

<template>
  <EmployeeLayout>
    <section class="scripts-page">
      <header class="scripts-page__header">
        <h2>标准话术</h2>
        <label>
          <span>场景分类</span>
          <select v-model="selectedCategory" @change="loadScripts">
            <option value="">全部</option>
            <option v-for="category in categories" :key="category" :value="category">
              {{ category }}
            </option>
          </select>
        </label>
      </header>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState
        v-else-if="!hasContent"
        state="empty"
        message="暂无可查看的标准话术"
      />

      <div v-else class="scripts-page__grid">
        <section>
          <h3>核心基础话术</h3>
          <div class="script-list">
            <RouterLink
              v-for="item in baseScripts"
              :key="item.id"
              class="script-card"
              :to="`/app/scripts/${item.id}`"
            >
              <strong>{{ item.title }}</strong>
              <span v-for="point in item.summary_points" :key="point">{{ point }}</span>
              <small>更新时间：{{ formatDateTime(item.updated_at) }}</small>
              <small>更新级别：{{ updateLevelLabel(item.update_level) }}</small>
              <small>可见范围：{{ scopeLabel(item.scope_type) }}</small>
              <em>{{ permissionLabel(item.permission_level) }}</em>
            </RouterLink>
          </div>
        </section>

        <section>
          <h3>标准化话术条目</h3>
          <div class="script-list">
            <RouterLink
              v-for="item in standardScripts"
              :key="item.id"
              class="script-card"
              :to="`/app/scripts/${item.id}`"
            >
              <strong>{{ item.title }}</strong>
              <span v-if="item.scene">{{ item.scene }}</span>
              <span>{{ item.recommended_speech_summary }}</span>
              <small>更新时间：{{ formatDateTime(item.updated_at) }}</small>
              <small>更新级别：{{ updateLevelLabel(item.update_level) }}</small>
              <small>可见范围：{{ scopeLabel(item.scope_type) }}</small>
              <em>{{ permissionLabel(item.permission_level) }}</em>
            </RouterLink>
          </div>
        </section>
      </div>
    </section>
  </EmployeeLayout>
</template>

<style scoped>
.scripts-page__header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.scripts-page__header h2 {
  font-size: 22px;
  margin: 0;
}

.scripts-page__header label {
  display: grid;
  gap: 6px;
}

.scripts-page__header select {
  border: 1px solid #bcccdc;
  border-radius: 6px;
  font: inherit;
  min-height: 36px;
  padding: 0 10px;
}

.scripts-page__grid {
  display: grid;
  gap: 18px;
}

.scripts-page__grid h3 {
  font-size: 18px;
  margin: 0 0 10px;
}

.script-list {
  display: grid;
  gap: 12px;
}

.script-card {
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  color: #1f2933;
  display: grid;
  gap: 7px;
  padding: 16px;
  text-decoration: none;
}

.script-card span,
.script-card small,
.script-card em {
  color: #52606d;
  font-style: normal;
}
</style>
