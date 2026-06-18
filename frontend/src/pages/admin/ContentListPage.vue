<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  listAdminContents,
  offlineAdminContent,
  publishAdminContent,
  retryAdminContentIndex,
  type AdminContent,
} from '../../api/admin-content'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { contentTypeLabel, permissionLabel } from '../../utils/format'

const items = ref<AdminContent[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const state = ref<'loading' | 'ready' | 'service'>('loading')
const message = ref('')
const filters = reactive({
  content_type: '',
  status: '',
  permission_level: '',
  category: '',
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const statusLabels: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  offline: '已下线',
}

const indexLabels: Record<string, string> = {
  not_synced: '未同步',
  syncing: '同步中',
  synced: '已同步',
  failed: '同步失败',
}

async function loadContents() {
  if (items.value.length === 0) {
    state.value = 'loading'
  }
  try {
    const response = await listAdminContents({
      category: filters.category || undefined,
      content_type: filters.content_type || undefined,
      page: page.value,
      page_size: pageSize,
      permission_level: filters.permission_level || undefined,
      status: filters.status || undefined,
    })
    items.value = response.items
    total.value = response.total
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

async function applyFilters() {
  page.value = 1
  await loadContents()
}

async function changePage(nextPage: number) {
  page.value = nextPage
  await loadContents()
}

function canEdit(item: AdminContent) {
  return item.status !== 'offline'
}

function canPublish(item: AdminContent) {
  return item.status !== 'offline'
}

function canOffline(item: AdminContent) {
  return item.status === 'published'
}

function publishConfirmation(item: AdminContent) {
  const audience = item.permission_level === 'full' ? '管理员和完整权限员工' : '全部员工'
  const replaceText = item.current_version_id ? '本次发布会替换当前版本。' : '本次将生成首个正式版本。'
  return [
    `标题：${item.title}`,
    `内容类型：${contentTypeLabel(item.content_type)}`,
    `权限级别：${permissionLabel(item.permission_level)}`,
    `可见受众：${audience}`,
    replaceText,
  ].join('\n')
}

async function publish(item: AdminContent) {
  if (!window.confirm(publishConfirmation(item))) {
    return
  }
  message.value = ''
  try {
    const result = await publishAdminContent(item.id)
    message.value =
      result.index_status === 'failed'
        ? '内容已发布，但 AI 检索暂不可用'
        : '内容发布成功'
    await loadContents()
  } catch {
    message.value = '发布失败，请稍后重试'
  }
}

async function offline(item: AdminContent) {
  if (!window.confirm(`确认下线“${item.title}”吗？下线后员工端和 AI 检索将不可见。`)) {
    return
  }
  try {
    await offlineAdminContent(item.id)
    message.value = '内容已下线'
    await loadContents()
  } catch {
    message.value = '下线失败，请稍后重试'
  }
}

async function retryIndex(item: AdminContent) {
  try {
    const result = await retryAdminContentIndex(item.id)
    message.value = result.index_status === 'synced' ? '索引同步成功' : '索引同步仍未完成'
    await loadContents()
  } catch {
    message.value = '索引重试失败，请稍后重试'
  }
}

onMounted(loadContents)
</script>

<template>
  <AdminLayout>
    <section class="admin-page">
      <header class="admin-page__title">
        <div>
          <h2>内容管理</h2>
          <p>维护草稿、发布版本并查看 AI 索引状态。</p>
        </div>
        <RouterLink class="admin-button admin-button--primary" to="/admin/contents/new">
          新建内容
        </RouterLink>
      </header>

      <form class="admin-filters" @submit.prevent="applyFilters">
        <label>
          <span>内容类型</span>
          <select v-model="filters.content_type">
            <option value="">全部</option>
            <option value="base_script">核心基础话术</option>
            <option value="standard_script">标准化话术</option>
            <option value="must_read">最新必读</option>
          </select>
        </label>
        <label>
          <span>内容状态</span>
          <select v-model="filters.status">
            <option value="">全部</option>
            <option value="draft">草稿</option>
            <option value="published">已发布</option>
            <option value="offline">已下线</option>
          </select>
        </label>
        <label>
          <span>权限级别</span>
          <select v-model="filters.permission_level">
            <option value="">全部</option>
            <option value="general">通用级</option>
            <option value="full">全量级</option>
          </select>
        </label>
        <label>
          <span>分类</span>
          <input v-model.trim="filters.category" type="text" />
        </label>
        <button class="admin-button" type="submit">筛选</button>
      </form>

      <p v-if="message" class="admin-notice">{{ message }}</p>
      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="items.length === 0" state="empty" message="暂无内容" />

      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>标题</th>
              <th>类型 / 分类</th>
              <th>权限</th>
              <th>状态</th>
              <th>版本</th>
              <th>索引状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>{{ item.title }}</td>
              <td>{{ contentTypeLabel(item.content_type) }} / {{ item.category || '-' }}</td>
              <td>{{ permissionLabel(item.permission_level) }}</td>
              <td>{{ statusLabels[item.status] }}</td>
              <td>{{ item.current_version_no ? `v${item.current_version_no}` : '-' }}</td>
              <td>
                <span class="status-tag" :data-status="item.index_status">
                  {{ indexLabels[item.index_status] || item.index_status }}
                </span>
              </td>
              <td>
                <div class="admin-actions">
                  <RouterLink
                    v-if="canEdit(item)"
                    class="admin-link"
                    :to="`/admin/contents/${item.id}/edit`"
                  >
                    编辑
                  </RouterLink>
                  <button v-if="canPublish(item)" type="button" @click="publish(item)">
                    发布
                  </button>
                  <button v-if="canOffline(item)" type="button" @click="offline(item)">
                    下线
                  </button>
                  <RouterLink
                    v-if="item.current_version_id"
                    class="admin-link"
                    :to="`/admin/contents/${item.id}/versions`"
                  >
                    历史
                  </RouterLink>
                  <button
                    v-if="item.index_status === 'failed'"
                    type="button"
                    @click="retryIndex(item)"
                  >
                    重试索引
                  </button>
                </div>
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
