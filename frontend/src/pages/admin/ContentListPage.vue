<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  deleteAdminContentDraft,
  listAdminContents,
  listAdminContentCategories,
  offlineAdminContent,
  publishAdminContent,
  retryAdminContentIndex,
  type AdminContent,
  type AdminContentPublishPayload,
} from '../../api/admin-content'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { FIXED_CONTENT_CATEGORIES } from '../../constants/content-options'
import { adminScopeLabel, contentTypeLabel, permissionLabel, updateLevelLabel } from '../../utils/format'

const items = ref<AdminContent[]>([])
const total = ref(0)
const page = ref(1)
const historyCategories = ref<string[]>([])
const pageSize = 20
const state = ref<'loading' | 'ready' | 'service'>('loading')
const message = ref('')
type PendingAction = 'publish' | 'offline' | 'retry' | 'delete'
const pendingActions = reactive<Record<number, PendingAction | undefined>>({})
const filters = reactive({
  content_type: '',
  status: '',
  permission_level: '',
  category: '',
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const categorySuggestions = computed(() => {
  const merged = new Set<string>()
  for (const category of [...FIXED_CONTENT_CATEGORIES, ...historyCategories.value]) {
    const normalized = category.trim()
    if (normalized) {
      merged.add(normalized)
    }
  }
  return Array.from(merged)
})

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

type UpdateLevel = AdminContentPublishPayload['update_level']

const publishDialog = reactive({
  open: false,
  item: null as AdminContent | null,
  update_level: 'major' as UpdateLevel,
  change_summary: '',
})

const publishDialogDetails = computed(() =>
  publishDialog.item ? publishConfirmation(publishDialog.item).split('\n') : [],
)

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

async function loadCategories() {
  try {
    const response = await listAdminContentCategories()
    historyCategories.value = response.items.filter(
      (item): item is string => typeof item === 'string',
    )
  } catch {
    historyCategories.value = []
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

function canDeleteDraft(item: AdminContent) {
  return item.status === 'draft' && item.current_version_id === null
}

function isPending(item: AdminContent) {
  return Boolean(pendingActions[item.id])
}

function isPublishConfirmed(item: AdminContent) {
  return item.status === 'published' && item.current_version_id !== null
}

function publishConfirmation(item: AdminContent) {
  const scope = adminScopeLabel(item.scope_type, item.department_name)
  const audience =
    item.scope_type === 'department'
      ? item.permission_level === 'full'
        ? '该部门全量员工和管理员'
        : '该部门所有员工和管理员'
      : item.permission_level === 'full'
        ? '全公司全量员工和管理员'
        : '全公司所有员工和管理员'
  const replaceText = item.current_version_id ? '本次发布会替换当前版本。' : '本次将生成首个正式版本。'
  return [
    `标题：${item.title}`,
    `内容类型：${contentTypeLabel(item.content_type)}`,
    `可见范围：${scope}`,
    `权限级别：${permissionLabel(item.permission_level)}`,
    `发布后影响范围：${audience}`,
    replaceText,
  ].join('\n')
}

function defaultPublishLevel(item: AdminContent): UpdateLevel {
  return item.current_version_id ? 'minor' : 'major'
}

function openPublishDialog(item: AdminContent) {
  if (isPending(item)) {
    return
  }
  message.value = ''
  publishDialog.item = item
  publishDialog.update_level = defaultPublishLevel(item)
  publishDialog.change_summary = ''
  publishDialog.open = true
}

function closePublishDialog(force = false) {
  if (!force && publishDialog.item && pendingActions[publishDialog.item.id] === 'publish') {
    return
  }
  publishDialog.open = false
  publishDialog.item = null
  publishDialog.change_summary = ''
}

function publishSuccessMessage(result: AdminContent) {
  if (result.index_status === 'failed') {
    return '内容已发布，但 AI 检索暂不可用'
  }
  if (result.quiz_generation_status === 'pending') {
    return '内容已发布；AI 候选题可在历史版本页生成'
  }
  if (result.quiz_generation_status === 'failed') {
    return '内容已发布；AI 候选题生成失败，可在历史版本页重试'
  }
  if (result.quiz_generation_status === 'completed') {
    return '内容已发布；AI 候选题已生成，待管理员审核'
  }
  return '内容发布成功'
}

async function confirmPublish() {
  const item = publishDialog.item
  if (!item) {
    return
  }
  if (isPending(item)) {
    return
  }
  message.value = ''
  const publishPayload: AdminContentPublishPayload = {
    update_level: publishDialog.update_level,
    change_summary: publishDialog.change_summary.trim() || null,
  }
  pendingActions[item.id] = 'publish'
  try {
    const result = await publishAdminContent(item.id, publishPayload)
    if (!isPublishConfirmed(result)) {
      message.value = '发布未完成，请刷新后确认内容状态'
    } else {
      message.value = publishSuccessMessage(result)
    }
    closePublishDialog(true)
    await loadContents()
  } catch {
    message.value = '发布失败，请稍后重试'
  } finally {
    delete pendingActions[item.id]
  }
}

async function offline(item: AdminContent) {
  if (isPending(item)) {
    return
  }
  if (!window.confirm(`确认下线“${item.title}”吗？下线后员工端和 AI 检索将不可见。`)) {
    return
  }
  pendingActions[item.id] = 'offline'
  try {
    await offlineAdminContent(item.id)
    message.value = '内容已下线'
    await loadContents()
  } catch {
    message.value = '下线失败，请稍后重试'
  } finally {
    delete pendingActions[item.id]
  }
}

async function retryIndex(item: AdminContent) {
  if (isPending(item)) {
    return
  }
  pendingActions[item.id] = 'retry'
  try {
    const result = await retryAdminContentIndex(item.id)
    message.value = result.index_status === 'synced' ? '索引同步成功' : '索引同步仍未完成'
    await loadContents()
  } catch {
    message.value = '索引重试失败，请稍后重试'
  } finally {
    delete pendingActions[item.id]
  }
}

async function deleteDraft(item: AdminContent) {
  if (isPending(item)) {
    return
  }
  if (!window.confirm('确定删除这个草稿吗？删除后不可恢复。')) {
    return
  }
  pendingActions[item.id] = 'delete'
  try {
    await deleteAdminContentDraft(item.id)
    message.value = '草稿已删除'
    await loadContents()
  } catch {
    message.value = '草稿删除失败，请稍后重试'
  } finally {
    delete pendingActions[item.id]
  }
}

onMounted(async () => {
  await Promise.all([loadContents(), loadCategories()])
})
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
          <input
            v-model.trim="filters.category"
            type="text"
            list="admin-content-filter-category-options"
          />
          <datalist id="admin-content-filter-category-options">
            <option v-for="category in categorySuggestions" :key="category" :value="category" />
          </datalist>
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
              <th>可见范围</th>
              <th>权限</th>
              <th>状态</th>
              <th>版本</th>
              <th>更新级别</th>
              <th>索引状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>{{ item.title }}</td>
              <td>{{ contentTypeLabel(item.content_type) }} / {{ item.category || '-' }}</td>
              <td>{{ adminScopeLabel(item.scope_type, item.department_name) }}</td>
              <td>{{ permissionLabel(item.permission_level) }}</td>
              <td>{{ statusLabels[item.status] }}</td>
              <td>{{ item.current_version_no ? `v${item.current_version_no}` : '-' }}</td>
              <td>{{ updateLevelLabel(item.current_update_level) }}</td>
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
                  <button
                    v-if="canPublish(item)"
                    type="button"
                    :disabled="isPending(item)"
                    @click="openPublishDialog(item)"
                  >
                    {{ pendingActions[item.id] === 'publish' ? '发布中' : '发布' }}
                  </button>
                  <button
                    v-if="canOffline(item)"
                    type="button"
                    :disabled="isPending(item)"
                    @click="offline(item)"
                  >
                    {{ pendingActions[item.id] === 'offline' ? '下线中' : '下线' }}
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
                    :disabled="isPending(item)"
                    @click="retryIndex(item)"
                  >
                    {{ pendingActions[item.id] === 'retry' ? '重试中' : '重试索引' }}
                  </button>
                  <button
                    v-if="canDeleteDraft(item)"
                    type="button"
                    :disabled="isPending(item)"
                    @click="deleteDraft(item)"
                  >
                    {{ pendingActions[item.id] === 'delete' ? '删除中' : '删除草稿' }}
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

      <div v-if="publishDialog.open && publishDialog.item" class="publish-dialog-backdrop">
        <section
          class="publish-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="publish-dialog-title"
        >
          <header class="publish-dialog__header">
            <div>
              <h3 id="publish-dialog-title">发布内容</h3>
              <p>{{ publishDialog.item.title }}</p>
            </div>
            <button
              class="admin-button"
              type="button"
              :disabled="pendingActions[publishDialog.item.id] === 'publish'"
              @click="closePublishDialog()"
            >
              取消
            </button>
          </header>
          <ul class="publish-dialog__details">
            <li v-for="line in publishDialogDetails" :key="line">{{ line }}</li>
          </ul>
          <label>
            <span>更新级别</span>
            <select v-model="publishDialog.update_level">
              <option value="minor">小更新</option>
              <option value="medium">中更新</option>
              <option value="major">大更新</option>
            </select>
          </label>
          <label>
            <span>变更摘要</span>
            <textarea v-model.trim="publishDialog.change_summary" rows="3" />
          </label>
          <div class="publish-dialog__actions">
            <button
              class="admin-button"
              type="button"
              :disabled="pendingActions[publishDialog.item.id] === 'publish'"
              @click="closePublishDialog()"
            >
              取消
            </button>
            <button
              class="admin-button admin-button--primary"
              type="button"
              :disabled="pendingActions[publishDialog.item.id] === 'publish'"
              @click="confirmPublish"
            >
              {{ pendingActions[publishDialog.item.id] === 'publish' ? '发布中' : '确认发布' }}
            </button>
          </div>
        </section>
      </div>
    </section>
  </AdminLayout>
</template>

<style scoped>
.publish-dialog-backdrop {
  align-items: center;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  inset: 0;
  justify-content: center;
  padding: 24px;
  position: fixed;
  z-index: 60;
}

.publish-dialog {
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.22);
  display: grid;
  gap: 16px;
  max-height: calc(100vh - 48px);
  max-width: 560px;
  overflow: auto;
  padding: 20px;
  width: min(560px, 100%);
}

.publish-dialog__header,
.publish-dialog__actions {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.publish-dialog__header h3,
.publish-dialog__header p {
  margin: 0;
}

.publish-dialog__header p {
  color: #475569;
  margin-top: 4px;
  overflow-wrap: anywhere;
}

.publish-dialog__details {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #334155;
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 12px 12px 12px 28px;
}

.publish-dialog label {
  color: #0f172a;
  display: grid;
  gap: 6px;
}

.publish-dialog select,
.publish-dialog textarea {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  color: #0f172a;
  font: inherit;
  padding: 8px 10px;
  width: 100%;
}
</style>
