<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  createAdminQuizQuestion,
  listAdminQuizQuestions,
  listAdminQuizSets,
  reviewAdminQuizQuestion,
  setAdminQuizQuestionStatus,
  updateAdminQuizQuestion,
  type AdminQuizQuestion,
  type AdminQuizPayload,
  type AdminQuizSet,
} from '../../api/admin-quiz'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { formatDateTime, permissionLabel } from '../../utils/format'

const items = ref<AdminQuizQuestion[]>([])
const quizSets = ref<AdminQuizSet[]>([])
const state = ref<'loading' | 'ready' | 'service'>('loading')
const editingId = ref<number | null>(null)
const showEditor = ref(false)
const error = ref('')
const message = ref('')
const pendingQuestionActionId = ref<number | null>(null)

const sourceLabels: Record<AdminQuizQuestion['source_type'], string> = {
  manual: '人工',
  ai_generated: 'AI 生成',
  ai_assisted: 'AI 辅助',
}

const reviewStatusLabels: Record<AdminQuizQuestion['review_status'], string> = {
  draft: '草稿',
  pending_review: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
}

const sourceInvalidReasonLabels: Record<
  NonNullable<AdminQuizQuestion['source_invalid_reason']>,
  string
> = {
  source_content_missing: '源内容不存在',
  source_content_offline: '源内容已下线',
  source_content_inactive: '源内容未发布',
  source_content_no_current_version: '源内容无当前版本',
  source_version_stale: '源版本已失效',
  quiz_set_inactive: '专题包已停用',
}

const form = reactive({
  question: '',
  options: '',
  answer: '',
  explanation: '',
  related_content_id: '',
  related_version_id: '',
  permission_level: 'general',
  status: 'enabled',
  source_type: 'manual',
  review_status: 'approved',
  generation_batch_id: '',
  needs_review: false,
  review_reason: '',
  expires_at: '',
  priority: 0,
})

function optionText(option: string | { label?: string; value?: string }) {
  return typeof option === 'string' ? option : (option.value ?? option.label ?? '')
}

async function loadQuestions() {
  if (items.value.length === 0) {
    state.value = 'loading'
  }
  try {
    const [response, setResponse] = await Promise.all([
      listAdminQuizQuestions(),
      listAdminQuizSets(),
    ])
    items.value = response.items
    quizSets.value = setResponse.items
    state.value = 'ready'
  } catch {
    state.value = 'service'
  }
}

function resetEditor() {
  editingId.value = null
  form.question = ''
  form.options = ''
  form.answer = ''
  form.explanation = ''
  form.related_content_id = ''
  form.related_version_id = ''
  form.permission_level = 'general'
  form.status = 'enabled'
  form.source_type = 'manual'
  form.review_status = 'approved'
  form.generation_batch_id = ''
  form.needs_review = false
  form.review_reason = ''
  form.expires_at = ''
  form.priority = 0
  error.value = ''
}

function startCreate() {
  resetEditor()
  showEditor.value = true
}

function startEdit(item: AdminQuizQuestion) {
  editingId.value = item.id
  form.question = item.question
  form.options = item.options.map(optionText).join('\n')
  form.answer = item.answer
  form.explanation = item.explanation || ''
  form.related_content_id = item.related_content_id ? String(item.related_content_id) : ''
  form.related_version_id = item.related_version_id ? String(item.related_version_id) : ''
  form.permission_level = item.permission_level
  form.status = item.status
  form.source_type = item.source_type
  form.review_status = item.review_status
  form.generation_batch_id = item.generation_batch_id ? String(item.generation_batch_id) : ''
  form.needs_review = item.needs_review
  form.review_reason = item.review_reason || ''
  form.expires_at = item.expires_at || ''
  form.priority = item.priority
  error.value = ''
  showEditor.value = true
}

function buildPayload(): AdminQuizPayload {
  return {
    question: form.question,
    options: form.options
      .split('\n')
      .map((option) => option.trim())
      .filter(Boolean),
    answer: form.answer,
    explanation: form.explanation || null,
    related_content_id: form.related_content_id ? Number(form.related_content_id) : null,
    related_version_id: form.related_version_id ? Number(form.related_version_id) : null,
    permission_level: form.permission_level as AdminQuizPayload['permission_level'],
    status: form.status as AdminQuizPayload['status'],
    source_type: form.source_type as AdminQuizPayload['source_type'],
    review_status: form.review_status as AdminQuizPayload['review_status'],
    generation_batch_id: form.generation_batch_id ? Number(form.generation_batch_id) : null,
    needs_review: form.needs_review,
    review_reason: form.review_reason || null,
    expires_at: form.expires_at || null,
    priority: Number(form.priority) || 0,
  }
}

async function saveQuestion() {
  const payload = buildPayload()
  if (!payload.question || payload.options.length < 2 || !payload.answer || !payload.explanation) {
    error.value = '请完整填写题干、至少两个选项、正确答案和解析'
    return
  }
  try {
    if (editingId.value) {
      await updateAdminQuizQuestion(editingId.value, payload)
    } else {
      await createAdminQuizQuestion(payload)
    }
    message.value = '测验题已保存'
    showEditor.value = false
    resetEditor()
    await loadQuestions()
  } catch {
    error.value = '测验题保存失败，请稍后重试'
  }
}

async function setStatus(item: AdminQuizQuestion, status: AdminQuizQuestion['status']) {
  pendingQuestionActionId.value = item.id
  try {
    await setAdminQuizQuestionStatus(item.id, status)
    await loadQuestions()
    const refreshed = items.value.find((candidate) => candidate.id === item.id)
    if (refreshed) {
      refreshed.status = status
    }
    message.value = status === 'enabled' ? '测验题已启用' : '测验题已禁用'
  } catch (caught) {
    const apiError = caught as { code?: string; message?: string }
    message.value =
      apiError.code === 'quiz_source_invalid'
        ? apiError.message || '来源已失效，不能启用该题目'
        : '状态更新失败，请稍后重试'
  } finally {
    pendingQuestionActionId.value = null
  }
}

function isSourceValid(item: AdminQuizQuestion) {
  return item.source_valid !== false
}

function sourceStateLabel(item: AdminQuizQuestion) {
  if (isSourceValid(item)) {
    return '来源有效'
  }
  return item.source_invalid_reason
    ? sourceInvalidReasonLabels[item.source_invalid_reason]
    : '来源已失效'
}

function isReviewCandidate(item: AdminQuizQuestion) {
  return item.review_status === 'draft' || item.review_status === 'pending_review'
}

function canApprove(item: AdminQuizQuestion) {
  return isSourceValid(item) && isReviewCandidate(item)
}

function canReject(item: AdminQuizQuestion) {
  return isReviewCandidate(item)
}

function canToggleStatus(item: AdminQuizQuestion) {
  return isSourceValid(item) && item.review_status === 'approved'
}

function shouldShowReviewActions(item: AdminQuizQuestion) {
  return canApprove(item) || canReject(item)
}

function isQuestionActionPending(item: AdminQuizQuestion) {
  return pendingQuestionActionId.value === item.id
}

async function reviewQuestion(item: AdminQuizQuestion, action: 'approve' | 'reject') {
  pendingQuestionActionId.value = item.id
  try {
    await reviewAdminQuizQuestion(item.id, action)
    await loadQuestions()
    message.value = action === 'approve' ? '测验题已审核通过并启用' : '测验题已驳回'
  } catch (caught) {
    const apiError = caught as { code?: string; message?: string }
    if (apiError.code === 'quiz_source_invalid') {
      message.value = apiError.message || '来源已失效，不能审核通过该题目'
    } else {
      message.value = action === 'approve' ? '审核通过失败，请稍后重试' : '驳回失败，请稍后重试'
    }
  } finally {
    pendingQuestionActionId.value = null
  }
}

onMounted(loadQuestions)
</script>

<template>
  <AdminLayout>
    <section class="admin-page">
      <header class="admin-page__title">
        <div>
          <h2>测验题管理</h2>
          <p>维护员工巩固测试题，题目仍由后端按权限过滤。</p>
        </div>
        <button class="admin-button admin-button--primary" type="button" @click="startCreate">
          新建测验题
        </button>
      </header>

      <p v-if="message" class="admin-notice">{{ message }}</p>

      <section v-if="quizSets.length > 0" class="admin-panel">
        <h3>大更新专题测验包</h3>
        <div class="admin-table-wrap">
          <table class="admin-table">
            <thead>
              <tr>
                <th>专题包</th>
                <th>关联版本</th>
                <th>权限</th>
                <th>题目数</th>
                <th>状态</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="quizSet in quizSets" :key="quizSet.id">
                <td>
                  <strong>{{ quizSet.title }}</strong>
                  <p v-if="quizSet.description">{{ quizSet.description }}</p>
                </td>
                <td>vID {{ quizSet.related_version_id }}</td>
                <td>{{ permissionLabel(quizSet.permission_level) }}</td>
                <td>{{ quizSet.question_count }}</td>
                <td>{{ quizSet.status === 'active' ? '启用' : '停用' }}</td>
                <td>{{ formatDateTime(quizSet.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <form v-if="showEditor" class="admin-form admin-panel" @submit.prevent="saveQuestion">
        <label class="admin-form__wide">
          <span>题干</span>
          <textarea v-model.trim="form.question" rows="3" />
        </label>
        <label class="admin-form__wide">
          <span>选项（每行一个）</span>
          <textarea v-model="form.options" rows="4" />
        </label>
        <label>
          <span>正确答案</span>
          <input v-model.trim="form.answer" type="text" />
        </label>
        <label class="admin-form__wide">
          <span>解析</span>
          <textarea v-model.trim="form.explanation" rows="3" />
        </label>
        <label>
          <span>关联话术 ID</span>
          <input v-model="form.related_content_id" type="number" min="1" />
        </label>
        <label>
          <span>关联版本 ID</span>
          <input v-model="form.related_version_id" type="number" min="1" />
        </label>
        <label>
          <span>权限级别</span>
          <select v-model="form.permission_level">
            <option value="general">通用级</option>
            <option value="full">全量级</option>
          </select>
        </label>
        <label>
          <span>状态</span>
          <select v-model="form.status">
            <option value="enabled">启用</option>
            <option value="disabled">禁用</option>
          </select>
        </label>
        <label>
          <span>题目来源</span>
          <select v-model="form.source_type">
            <option value="manual">人工</option>
            <option value="ai_generated">AI 生成</option>
            <option value="ai_assisted">AI 辅助</option>
          </select>
        </label>
        <label>
          <span>审核状态</span>
          <select v-model="form.review_status">
            <option value="draft">草稿</option>
            <option value="pending_review">待审核</option>
            <option value="approved">已通过</option>
            <option value="rejected">已拒绝</option>
          </select>
        </label>
        <label>
          <span>生成批次 ID</span>
          <input v-model="form.generation_batch_id" type="number" min="1" />
        </label>
        <label>
          <span>抽题优先级</span>
          <input v-model.number="form.priority" type="number" min="0" />
        </label>
        <label>
          <span>过期时间</span>
          <input v-model.trim="form.expires_at" type="text" placeholder="2026-06-30T23:59:59" />
        </label>
        <label>
          <span>是否待复核</span>
          <select v-model="form.needs_review">
            <option :value="false">否</option>
            <option :value="true">是</option>
          </select>
        </label>
        <label class="admin-form__wide">
          <span>复核原因</span>
          <textarea v-model.trim="form.review_reason" rows="2" />
        </label>
        <p v-if="error" class="admin-error">{{ error }}</p>
        <div class="admin-form__actions">
          <button class="admin-button admin-button--primary" type="submit">保存测验题</button>
          <button class="admin-button" type="button" @click="showEditor = false">取消</button>
        </div>
      </form>

      <AppState v-if="state === 'loading'" state="loading" />
      <AppState v-else-if="state === 'service'" state="service" />
      <AppState v-else-if="items.length === 0" state="empty" message="暂无测验题" />
      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>题干</th>
              <th>权限</th>
              <th>关联话术</th>
              <th>关联版本</th>
              <th>批次 / 优先级</th>
              <th>来源 / 审核</th>
              <th>来源状态</th>
              <th>复核</th>
              <th>状态</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>{{ item.question }}</td>
              <td>{{ permissionLabel(item.permission_level) }}</td>
              <td>{{ item.related_content_title || item.related_content_id || '-' }}</td>
              <td>{{ item.related_version_id || '-' }}</td>
              <td>
                <span>批次：{{ item.generation_batch_id || '-' }}</span>
                <br />
                <span>优先级：{{ item.priority }}</span>
                <br />
                <span>过期：{{ item.expires_at ? formatDateTime(item.expires_at) : '-' }}</span>
              </td>
              <td>{{ sourceLabels[item.source_type] }} / {{ reviewStatusLabels[item.review_status] }}</td>
              <td>
                <span class="status-tag" :data-status="isSourceValid(item) ? 'synced' : 'failed'">
                  {{ sourceStateLabel(item) }}
                </span>
                <p v-if="!isSourceValid(item)" class="admin-muted">来源失效，禁止上线</p>
              </td>
              <td>{{ item.needs_review ? item.review_reason || '待复核' : '-' }}</td>
              <td>{{ item.status === 'enabled' ? '启用' : '禁用' }}</td>
              <td>{{ formatDateTime(item.updated_at) }}</td>
              <td>
                <div class="admin-actions">
                  <button type="button" @click="startEdit(item)">编辑</button>
                  <template v-if="shouldShowReviewActions(item)">
                    <button
                      v-if="canApprove(item)"
                      type="button"
                      :disabled="isQuestionActionPending(item)"
                      @click="reviewQuestion(item, 'approve')"
                    >
                      {{ isQuestionActionPending(item) ? '处理中...' : '审核通过并启用' }}
                    </button>
                    <button
                      v-if="canReject(item)"
                      type="button"
                      :disabled="isQuestionActionPending(item)"
                      @click="reviewQuestion(item, 'reject')"
                    >
                      {{ isQuestionActionPending(item) ? '处理中...' : '驳回' }}
                    </button>
                  </template>
                  <template v-else-if="canToggleStatus(item)">
                    <button
                      v-if="item.status === 'enabled'"
                      type="button"
                      :disabled="isQuestionActionPending(item)"
                      @click="setStatus(item, 'disabled')"
                    >
                      {{ isQuestionActionPending(item) ? '处理中...' : '禁用' }}
                    </button>
                    <button
                      v-else
                      type="button"
                      :disabled="isQuestionActionPending(item)"
                      @click="setStatus(item, 'enabled')"
                    >
                      {{ isQuestionActionPending(item) ? '处理中...' : '启用' }}
                    </button>
                  </template>
                  <span v-else class="admin-muted">无可用上线操作</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </AdminLayout>
</template>
