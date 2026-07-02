<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { listAdminDepartments, type Department } from '../../api/admin-departments'
import {
  createAdminContent,
  getAdminContent,
  listAdminContentCategories,
  listAdminContentScenes,
  parseAdminContentImport,
  updateAdminContent,
  type AdminContentPayload,
  type ContentImportDraft,
  type ContentImportResult,
  type ContentImportSplitSuggestion,
} from '../../api/admin-content'
import AdminLayout from '../../components/AdminLayout.vue'
import AppState from '../../components/AppState.vue'
import { FIXED_CONTENT_CATEGORIES } from '../../constants/content-options'

const route = useRoute()
const router = useRouter()
const contentId = computed(() => Number(route.params.contentId || 0))
const isEditing = computed(() => contentId.value > 0)
const state = ref<'ready' | 'loading' | 'service'>('ready')
const error = ref('')
const isSaving = ref(false)
const isImporting = ref(false)
const isSavingSplitDrafts = ref(false)
const departments = ref<Department[]>([])
const historyCategories = ref<string[]>([])
const historyScenes = ref<string[]>([])
const editorMode = ref<'manual' | 'import'>('import')
const importFile = ref<File | null>(null)
const importParseMode = ref<'fast' | 'enhanced'>('fast')
const importForceOcr = ref(false)
const importError = ref('')
const importResult = ref<ContentImportResult | null>(null)
const importStage = ref<'idle' | 'uploading' | 'extracting' | 'structuring' | 'filled' | 'failed'>(
  'idle',
)
const importProgress = ref(0)
const importTab = ref<'single' | 'split'>('single')
const selectedSuggestionIds = ref<Record<string, boolean>>({})
const activeSplitSuggestionId = ref('')
let importProgressTimer: number | null = null

function optionValues(values: unknown[]) {
  const merged = new Set<string>()
  for (const value of values) {
    const normalized = String(value ?? '').trim()
    if (normalized) {
      merged.add(normalized)
    }
  }
  return Array.from(merged)
}

const categorySuggestions = computed(() => {
  const importedCategories = importResult.value?.split_suggestions.map((suggestion) => suggestion.category) || []
  return optionValues([
    ...FIXED_CONTENT_CATEGORIES,
    ...historyCategories.value,
    ...importedCategories,
    form.category,
    editableSplitSuggestion.category,
  ])
})

const sceneSuggestions = computed(() => {
  const importedScenes =
    importResult.value?.split_suggestions
      .map((suggestion) => payloadText(suggestion.structured_payload || {}, 'scene'))
      .filter(Boolean) || []
  return optionValues([
    ...historyScenes.value,
    ...importedScenes,
    form.scene,
    editableSplitSuggestion.scene,
  ])
})

const form = reactive({
  title: '',
  content_type: '',
  category: '',
  permission_level: '',
  scope_type: 'global',
  department_id: null as number | null,
  summary: '',
  body: '',
  scene: '',
  recommended_speech: '',
  forbidden_speech: '',
  notes: '',
  update_body: '',
  adjustment_points: '',
})

const editableSplitSuggestion = reactive({
  title: '',
  category: '',
  summary: '',
  body: '',
  scene: '',
  recommended_speech: '',
  forbidden_speech: '',
  notes: '',
  update_body: '',
  adjustment_points: '',
})

const canParseImport = computed(() => Boolean(form.content_type && importFile.value && !isImporting.value))
const selectedSplitSuggestions = computed<ContentImportSplitSuggestion[]>(() => {
  if (!importResult.value) {
    return []
  }
  return importResult.value.split_suggestions.filter((suggestion) => selectedSuggestionIds.value[suggestion.temp_id])
})
const activeSplitSuggestion = computed<ContentImportSplitSuggestion | null>(() => {
  if (!importResult.value || !activeSplitSuggestionId.value) {
    return null
  }
  return (
    importResult.value.split_suggestions.find(
      (suggestion) => suggestion.temp_id === activeSplitSuggestionId.value,
    ) || null
  )
})
const canSaveSplitDrafts = computed(() =>
  Boolean(selectedSplitSuggestions.value.length && form.permission_level && !isSavingSplitDrafts.value),
)
const importWarnings = computed(() => {
  if (!importResult.value) {
    return []
  }
  const warnings = [
    ...(importResult.value.extraction_warnings || []),
    ...(importResult.value.structure_warnings || []),
    ...(importResult.value.warnings || []),
    ...(importResult.value.single_draft.warnings || []),
  ]
  return Array.from(new Set(warnings.filter(Boolean)))
})
const importStageLabel = computed(() => {
  if (importStage.value === 'uploading') {
    return '上传文件'
  }
  if (importStage.value === 'extracting') {
    return '解析正文和图片'
  }
  if (importStage.value === 'structuring') {
    return 'AI 结构化字段'
  }
  if (importStage.value === 'filled') {
    return '已填充草稿'
  }
  if (importStage.value === 'failed') {
    return '解析失败'
  }
  return '等待导入'
})

function applyContent(content: Awaited<ReturnType<typeof getAdminContent>>) {
  const payload = content.structured_payload || {}
  form.title = content.title
  form.content_type = content.content_type
  form.category = content.category || ''
  form.permission_level = content.permission_level
  form.scope_type = content.scope_type || 'global'
  form.department_id = content.department_id ?? null
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

async function loadDepartments() {
  try {
    const response = await listAdminDepartments(false)
    departments.value = response.items
  } catch {
    departments.value = []
  }
}

async function loadCategories() {
  try {
    const response = await listAdminContentCategories()
    historyCategories.value = response.items
  } catch {
    historyCategories.value = []
  }
}

async function loadScenes() {
  try {
    const response = await listAdminContentScenes()
    historyScenes.value = response.items.filter((item): item is string => typeof item === 'string')
  } catch {
    historyScenes.value = []
  }
}

function lines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

function hasDraftInput() {
  return Boolean(
    form.title ||
      form.category ||
      form.summary ||
      form.body ||
      form.scene ||
      form.recommended_speech ||
      form.forbidden_speech ||
      form.notes ||
      form.update_body ||
      form.adjustment_points,
  )
}

function resetImportProgress() {
  if (importProgressTimer !== null) {
    window.clearInterval(importProgressTimer)
    importProgressTimer = null
  }
}

function startImportProgress() {
  resetImportProgress()
  importStage.value = 'uploading'
  importProgress.value = 5
  importProgressTimer = window.setInterval(() => {
    if (importProgress.value >= 88) {
      return
    }
    const nextIncrement = Math.max(1, Math.ceil((88 - importProgress.value) * 0.08))
    importProgress.value = Math.min(88, importProgress.value + nextIncrement)
    if (importProgress.value >= 20 && importStage.value === 'uploading') {
      importStage.value = 'extracting'
    }
    if (importProgress.value >= 55 && importStage.value === 'extracting') {
      importStage.value = 'structuring'
    }
  }, 500)
}

function finishImportProgress(success: boolean) {
  resetImportProgress()
  importStage.value = success ? 'filled' : 'failed'
  importProgress.value = success ? 100 : Math.max(importProgress.value, 1)
}

function applyImportedDraft(draft: ContentImportDraft) {
  const payload = draft.structured_payload || {}
  form.title = draft.title || form.title
  form.category = draft.category || form.category
  form.summary = draft.summary || form.summary
  form.body = draft.body || form.body
  form.scene = String(payload.scene || '')
  form.recommended_speech = String(payload.recommended_speech || '')
  form.forbidden_speech = String(payload.forbidden_speech || '')
  form.notes = String(payload.notes || '')
  form.update_body = String(payload.update_body || draft.body || '')
  form.adjustment_points = Array.isArray(payload.adjustment_points)
    ? payload.adjustment_points.join('\n')
    : ''
}

function onImportFileChange(event: Event) {
  importError.value = ''
  const input = event.target as HTMLInputElement
  importFile.value = input.files?.[0] ?? null
}

async function parseImportFile() {
  importError.value = ''
  if (!form.content_type || !importFile.value) {
    importError.value = '请先选择内容类型和导入文件'
    return
  }
  const extension = importFile.value.name.toLowerCase().slice(importFile.value.name.lastIndexOf('.'))
  if (extension === '.doc') {
    importError.value = '仅支持 .docx 和 .pdf。老版 .doc 文件请另存为 .docx 后上传。'
    return
  }
  if (!['.docx', '.pdf'].includes(extension)) {
    importError.value = '仅支持 .docx 和 .pdf。'
    return
  }
  if (hasDraftInput() && !window.confirm('解析结果会覆盖当前表单内容，是否继续？')) {
    return
  }
  isImporting.value = true
  importResult.value = null
  activeSplitSuggestionId.value = ''
  startImportProgress()
  try {
    const result = await parseAdminContentImport({
      content_type: form.content_type as AdminContentPayload['content_type'],
      parse_mode: importParseMode.value,
      force_ocr: importForceOcr.value,
      file: importFile.value,
    })
    importResult.value = result
    importTab.value = 'single'
    selectedSuggestionIds.value = Object.fromEntries(
      result.split_suggestions.map((suggestion) => [suggestion.temp_id, suggestion.confidence !== 'low']),
    )
    applyImportedDraft(result.single_draft)
    finishImportProgress(true)
  } catch (caught) {
    const apiError = caught as { message?: string }
    finishImportProgress(false)
    importError.value = apiError.message || '解析失败，请检查文件或稍后重试'
  } finally {
    isImporting.value = false
  }
}

function buildImportedDraftPayload(
  draft: ContentImportDraft,
  contentType: AdminContentPayload['content_type'],
): AdminContentPayload {
  const payload: AdminContentPayload = {
    content_type: contentType,
    title: draft.title,
    category: draft.category || form.category,
    permission_level: form.permission_level as AdminContentPayload['permission_level'],
    summary: draft.summary,
    body: draft.body,
    structured_payload: draft.structured_payload || {},
  }
  if (form.scope_type === 'department') {
    payload.scope_type = 'department'
    payload.department_id = form.department_id
  }
  return payload
}

function isBlank(value: unknown) {
  if (Array.isArray(value)) {
    return value.length === 0
  }
  return String(value ?? '').trim() === ''
}

function payloadText(payload: Record<string, unknown>, key: string) {
  return String(payload[key] ?? '')
}

function payloadLines(payload: Record<string, unknown>, key: string) {
  const value = payload[key]
  if (Array.isArray(value)) {
    return value.filter((item) => !isBlank(item))
  }
  return lines(String(value ?? ''))
}

function missingFieldsForImportedDraft(
  draft: ContentImportDraft,
  contentType: AdminContentPayload['content_type'],
) {
  const missing: string[] = []
  const payload = draft.structured_payload || {}
  const addMissing = (label: string) => {
    if (!missing.includes(label)) {
      missing.push(label)
    }
  }

  if (isBlank(draft.title)) {
    addMissing('标题')
  }
  if (isBlank(draft.category || form.category)) {
    addMissing('分类')
  }
  if (isBlank(draft.summary)) {
    addMissing('摘要')
  }
  if (isBlank(draft.body)) {
    addMissing('正文')
  }
  if (contentType === 'standard_script') {
    if (isBlank(payload.scene)) {
      addMissing('场景')
    }
    if (isBlank(payload.recommended_speech)) {
      addMissing('推荐说法')
    }
  }
  if (contentType === 'must_read') {
    if (isBlank(payload.update_body)) {
      addMissing('更新正文')
    }
    if (payloadLines(payload, 'adjustment_points').length === 0) {
      addMissing('调整要点')
    }
  }

  for (const field of (draft as Partial<ContentImportSplitSuggestion>).missing_fields || []) {
    addMissing(field)
  }
  return missing
}

function isImportedDraftComplete(draft: ContentImportDraft, contentType: AdminContentPayload['content_type']) {
  return missingFieldsForImportedDraft(draft, contentType).length === 0
}

function splitSuggestionMissingFields(suggestion: ContentImportSplitSuggestion) {
  return missingFieldsForImportedDraft(suggestion, suggestion.suggested_content_type)
}

function isSplitSuggestionSaveable(suggestion: ContentImportSplitSuggestion) {
  return suggestion.is_saveable !== false && splitSuggestionMissingFields(suggestion).length === 0
}

function splitSuggestionStatusLabel(suggestion: ContentImportSplitSuggestion) {
  if (!isSplitSuggestionSaveable(suggestion) || suggestion.validation_status === 'invalid') {
    return '缺少字段'
  }
  if (
    suggestion.validation_status === 'warning' ||
    (suggestion.quality_warnings || []).length > 0 ||
    (suggestion.warnings || []).length > 0
  ) {
    return '建议核对'
  }
  return '可保存'
}

function splitSuggestionStatusType(suggestion: ContentImportSplitSuggestion) {
  if (!isSplitSuggestionSaveable(suggestion) || suggestion.validation_status === 'invalid') {
    return 'invalid'
  }
  if (
    suggestion.validation_status === 'warning' ||
    (suggestion.quality_warnings || []).length > 0 ||
    (suggestion.warnings || []).length > 0
  ) {
    return 'warning'
  }
  return 'valid'
}

function splitSuggestionWarnings(suggestion: ContentImportSplitSuggestion) {
  return Array.from(new Set([...(suggestion.quality_warnings || []), ...(suggestion.warnings || [])]))
}

function refreshSplitSuggestionValidation(
  suggestion: ContentImportSplitSuggestion,
): ContentImportSplitSuggestion {
  const draftForValidation: ContentImportSplitSuggestion = {
    ...suggestion,
    missing_fields: [],
  }
  const missingFields = missingFieldsForImportedDraft(
    draftForValidation,
    suggestion.suggested_content_type,
  )
  return {
    ...draftForValidation,
    missing_fields: missingFields,
    is_saveable: missingFields.length === 0,
    validation_status: missingFields.length
      ? 'invalid'
      : (suggestion.quality_warnings || []).length
        ? 'warning'
        : 'valid',
  }
}

function updateSplitSuggestionFromCard(
  source: ContentImportSplitSuggestion,
  event: Event,
  field: 'category' | 'scene',
) {
  if (!importResult.value) {
    return
  }
  const control = event.target as HTMLInputElement | HTMLSelectElement
  const value = control.value.trim()
  const index = importResult.value.split_suggestions.findIndex(
    (suggestion) => suggestion.temp_id === source.temp_id,
  )
  if (index < 0) {
    return
  }
  const current = importResult.value.split_suggestions[index]
  const edited: ContentImportSplitSuggestion =
    field === 'category'
      ? {
          ...current,
          category: value || null,
        }
      : {
          ...current,
          structured_payload: {
            ...(current.structured_payload || {}),
            scene: value,
          },
        }
  importResult.value.split_suggestions.splice(index, 1, refreshSplitSuggestionValidation(edited))
}

function formatInvalidSplitSuggestions(suggestions: ContentImportSplitSuggestion[]) {
  const detail = suggestions
    .map((suggestion) => {
      const fields = splitSuggestionMissingFields(suggestion)
      const fieldText = fields.length ? fields.join('、') : '必填字段'
      return `${suggestion.title || '未命名候选'}（${fieldText}）`
    })
    .join('；')
  return `以下拆解候选缺少必填字段，未保存：${detail}`
}

function openSplitSuggestionDetail(suggestion: ContentImportSplitSuggestion) {
  const payload = suggestion.structured_payload || {}
  activeSplitSuggestionId.value = suggestion.temp_id
  editableSplitSuggestion.title = suggestion.title || ''
  editableSplitSuggestion.category = suggestion.category || form.category || ''
  editableSplitSuggestion.summary = suggestion.summary || ''
  editableSplitSuggestion.body = suggestion.body || ''
  editableSplitSuggestion.scene = payloadText(payload, 'scene')
  editableSplitSuggestion.recommended_speech = payloadText(payload, 'recommended_speech')
  editableSplitSuggestion.forbidden_speech = payloadText(payload, 'forbidden_speech')
  editableSplitSuggestion.notes = payloadText(payload, 'notes')
  editableSplitSuggestion.update_body = payloadText(payload, 'update_body') || suggestion.body || ''
  editableSplitSuggestion.adjustment_points = payloadLines(payload, 'adjustment_points').join('\n')
}

function closeSplitSuggestionDetail() {
  activeSplitSuggestionId.value = ''
}

function buildEditedSplitSuggestion(source: ContentImportSplitSuggestion): ContentImportSplitSuggestion {
  let structuredPayload: Record<string, unknown> = source.structured_payload || {}
  if (source.suggested_content_type === 'standard_script') {
    structuredPayload = {
      scene: editableSplitSuggestion.scene.trim(),
      recommended_speech: editableSplitSuggestion.recommended_speech.trim(),
      forbidden_speech: editableSplitSuggestion.forbidden_speech.trim(),
      notes: editableSplitSuggestion.notes.trim(),
    }
  } else if (source.suggested_content_type === 'must_read') {
    structuredPayload = {
      update_body: editableSplitSuggestion.update_body.trim() || editableSplitSuggestion.body.trim(),
      adjustment_points: lines(editableSplitSuggestion.adjustment_points),
    }
  } else {
    structuredPayload = {
      ...structuredPayload,
      points: Array.isArray(structuredPayload.points)
        ? structuredPayload.points
        : lines(editableSplitSuggestion.summary),
    }
  }

  const edited: ContentImportSplitSuggestion = {
    ...source,
    title: editableSplitSuggestion.title.trim(),
    category: editableSplitSuggestion.category.trim() || null,
    summary: editableSplitSuggestion.summary.trim(),
    body: editableSplitSuggestion.body.trim(),
    structured_payload: structuredPayload,
    missing_fields: [],
  }
  return refreshSplitSuggestionValidation(edited)
}

function saveSplitSuggestionEdits() {
  if (!importResult.value || !activeSplitSuggestion.value) {
    return
  }
  const edited = buildEditedSplitSuggestion(activeSplitSuggestion.value)
  const index = importResult.value.split_suggestions.findIndex(
    (suggestion) => suggestion.temp_id === edited.temp_id,
  )
  if (index >= 0) {
    importResult.value.split_suggestions.splice(index, 1, edited)
    selectedSuggestionIds.value[edited.temp_id] = true
  }
}

async function saveSelectedSuggestions() {
  importError.value = ''
  if (!selectedSplitSuggestions.value.length) {
    importError.value = '请先勾选要保存的拆解候选'
    return
  }
  if (!form.permission_level) {
    importError.value = '请先选择权限级别'
    return
  }
  if (form.scope_type === 'department' && !form.department_id) {
    importError.value = '请选择限定部门'
    return
  }
  const saveableSuggestions = selectedSplitSuggestions.value.filter(isSplitSuggestionSaveable)
  const invalidSuggestions = selectedSplitSuggestions.value.filter(
    (suggestion) => !isSplitSuggestionSaveable(suggestion),
  )
  if (!saveableSuggestions.length) {
    importError.value = formatInvalidSplitSuggestions(invalidSuggestions)
    openSplitSuggestionDetail(invalidSuggestions[0])
    return
  }
  const invalidMessage = invalidSuggestions.length
    ? formatInvalidSplitSuggestions(invalidSuggestions)
    : ''
  if (invalidMessage) {
    importError.value = invalidMessage
    openSplitSuggestionDetail(invalidSuggestions[0])
  }
  isSavingSplitDrafts.value = true
  try {
    await Promise.all(
      saveableSuggestions.map((suggestion) =>
        createAdminContent(buildImportedDraftPayload(suggestion, suggestion.suggested_content_type)),
      ),
    )
    if (invalidSuggestions.length) {
      importError.value = invalidMessage
      openSplitSuggestionDetail(invalidSuggestions[0])
    } else {
      await router.push('/admin/contents')
    }
  } catch {
    importError.value = '拆解草稿保存失败，请稍后重试'
  } finally {
    isSavingSplitDrafts.value = false
  }
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
  if (form.scope_type === 'department' && !form.department_id) {
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

function onScopeTypeChange() {
  if (form.scope_type === 'global') {
    form.department_id = null
  }
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
    if (form.scope_type === 'department') {
      payload.scope_type = 'department'
      payload.department_id = form.department_id
    } else if (isEditing.value) {
      payload.scope_type = 'global'
      payload.department_id = null
    }
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

onMounted(async () => {
  await Promise.all([loadDepartments(), loadCategories(), loadScenes(), loadContent()])
})

onUnmounted(() => {
  resetImportProgress()
})
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

        <section v-if="!isEditing" class="admin-form__wide editor-mode-switch">
          <button
            type="button"
            :class="{ active: editorMode === 'manual' }"
            @click="editorMode = 'manual'"
          >
            人工添加
          </button>
          <button
            type="button"
            :class="{ active: editorMode === 'import' }"
            @click="editorMode = 'import'"
          >
            导入模式
          </button>
        </section>

        <section v-if="!isEditing && editorMode === 'import'" class="admin-form__wide import-panel">
          <header>
            <h3>从 Word/PDF 导入</h3>
            <p>支持 .docx / .pdf，解析结果只填入草稿表单，不会自动发布。</p>
          </header>
          <div class="import-panel__controls">
            <label>
              <span>导入文件</span>
              <input
                type="file"
                accept=".docx,.pdf"
                @change="onImportFileChange"
              />
            </label>
            <label>
              <span>解析模式</span>
              <select v-model="importParseMode">
                <option value="fast">快速解析</option>
                <option value="enhanced">增强解析</option>
              </select>
            </label>
            <label class="import-panel__check">
              <input v-model="importForceOcr" type="checkbox" />
              <span>强制 OCR</span>
            </label>
            <button
              class="admin-button"
              type="button"
              :disabled="!canParseImport"
              @click="parseImportFile"
            >
              {{ isImporting ? '解析中' : '解析并填入表单' }}
            </button>
          </div>
          <div v-if="isImporting || importProgress" class="import-panel__progress">
            <div class="import-panel__progress-meta">
              <span>{{ importStageLabel }}</span>
              <strong>{{ importProgress }}%</strong>
            </div>
            <progress :value="importProgress" max="100" />
          </div>
          <p v-if="importError" class="admin-error">{{ importError }}</p>
          <section v-if="importResult" class="import-result">
            <div class="import-result__tabs">
              <button
                type="button"
                :class="{ active: importTab === 'single' }"
                @click="importTab = 'single'"
              >
                单条草稿
              </button>
              <button
                type="button"
                :class="{ active: importTab === 'split' }"
                @click="importTab = 'split'"
              >
                拆解候选
              </button>
            </div>
            <div v-if="importTab === 'single'" class="import-result__body">
              <p v-if="importResult.structure_status === 'failed'" class="admin-error">
                AI 结构化失败：{{ importResult.structure_error_message || '已使用本地解析文本生成保守草稿' }}
              </p>
              <p v-else>AI 结构化完成</p>
              <p v-if="importResult.parse_trace">
                OCR：图片 {{ importResult.parse_trace.ocr_image_count }} / {{ importResult.parse_trace.image_count }}，
                失败 {{ importResult.parse_trace.ocr_failed_count }}，页面 {{ importResult.parse_trace.ocr_page_count }}
              </p>
              <p>解析方式：{{ importResult.parse_method }}</p>
              <p>已填入：{{ importResult.single_draft.title }}</p>
            </div>
            <div v-else class="import-result__body">
              <p v-if="!importResult.split_suggestions.length">未识别到可靠拆解边界，可使用单条草稿。</p>
              <article
                v-for="suggestion in importResult.split_suggestions"
                :key="suggestion.temp_id"
                class="import-result__candidate"
              >
                <div class="import-result__candidate-head">
                  <label class="import-result__candidate-toggle">
                    <input
                      v-model="selectedSuggestionIds[suggestion.temp_id]"
                      class="import-result__candidate-checkbox"
                      type="checkbox"
                    />
                    <span class="import-result__candidate-title">{{ suggestion.title }}</span>
                  </label>
                  <span
                    class="import-result__candidate-status"
                    :data-status="splitSuggestionStatusType(suggestion)"
                  >
                    {{ splitSuggestionStatusLabel(suggestion) }}
                  </span>
                </div>
                <div
                  class="import-result__candidate-fields"
                  :data-testid="`split-candidate-fields-${suggestion.temp_id}`"
                >
                  <label>
                    <span>候选分类</span>
                    <select
                      :value="suggestion.category || ''"
                      @change="updateSplitSuggestionFromCard(suggestion, $event, 'category')"
                    >
                      <option value="">请选择</option>
                      <option v-for="category in categorySuggestions" :key="category" :value="category">
                        {{ category }}
                      </option>
                    </select>
                  </label>
                  <label v-if="suggestion.suggested_content_type === 'standard_script'">
                    <span>候选场景</span>
                    <select
                      :value="payloadText(suggestion.structured_payload || {}, 'scene')"
                      @change="updateSplitSuggestionFromCard(suggestion, $event, 'scene')"
                    >
                      <option value="">请选择</option>
                      <option v-for="scene in sceneSuggestions" :key="scene" :value="scene">
                        {{ scene }}
                      </option>
                    </select>
                  </label>
                </div>
                <p>{{ suggestion.summary || suggestion.body.slice(0, 120) }}</p>
                <p v-if="splitSuggestionMissingFields(suggestion).length" class="admin-error">
                  缺少字段：{{ splitSuggestionMissingFields(suggestion).join('、') }}
                </p>
                <ul v-if="splitSuggestionWarnings(suggestion).length" class="import-result__warnings">
                  <li v-for="warning in splitSuggestionWarnings(suggestion)" :key="warning">
                    {{ warning }}
                  </li>
                </ul>
                <button class="admin-button" type="button" @click="openSplitSuggestionDetail(suggestion)">
                  查看并编辑
                </button>
              </article>
              <div v-if="activeSplitSuggestion" class="import-result__modal-backdrop">
                <section
                  class="import-result__detail import-result__detail--modal"
                  role="dialog"
                  aria-modal="true"
                  aria-labelledby="split-suggestion-dialog-title"
                >
                  <header class="import-result__detail-head">
                    <div>
                      <h4 id="split-suggestion-dialog-title">拆解候选详情</h4>
                      <p>{{ activeSplitSuggestion.title || '未命名候选' }}</p>
                    </div>
                    <button class="admin-button" type="button" @click="closeSplitSuggestionDetail">
                      关闭
                    </button>
                  </header>
                  <p v-if="splitSuggestionMissingFields(activeSplitSuggestion).length" class="admin-error">
                    缺少字段：{{ splitSuggestionMissingFields(activeSplitSuggestion).join('、') }}
                  </p>
                  <p class="import-result__detail-preview">{{ editableSplitSuggestion.body }}</p>
                  <div class="import-result__detail-grid">
                    <label>
                      <span>候选标题</span>
                      <input v-model.trim="editableSplitSuggestion.title" type="text" />
                    </label>
                    <label>
                      <span>候选分类</span>
                      <select v-model="editableSplitSuggestion.category">
                        <option value="">请选择</option>
                        <option v-for="category in categorySuggestions" :key="category" :value="category">
                          {{ category }}
                        </option>
                      </select>
                    </label>
                    <label class="admin-form__wide">
                      <span>候选摘要</span>
                      <textarea v-model.trim="editableSplitSuggestion.summary" rows="3" />
                    </label>
                    <label class="admin-form__wide">
                      <span>候选正文</span>
                      <textarea v-model.trim="editableSplitSuggestion.body" rows="6" />
                    </label>
                    <template v-if="activeSplitSuggestion.suggested_content_type === 'standard_script'">
                      <label>
                        <span>候选场景</span>
                        <select v-model="editableSplitSuggestion.scene">
                          <option value="">请选择</option>
                          <option v-for="scene in sceneSuggestions" :key="scene" :value="scene">
                            {{ scene }}
                          </option>
                        </select>
                      </label>
                      <label class="admin-form__wide">
                        <span>候选推荐说法</span>
                        <textarea v-model.trim="editableSplitSuggestion.recommended_speech" rows="4" />
                      </label>
                      <label class="admin-form__wide">
                        <span>候选禁用说法</span>
                        <textarea v-model.trim="editableSplitSuggestion.forbidden_speech" rows="3" />
                      </label>
                      <label class="admin-form__wide">
                        <span>候选注意事项</span>
                        <textarea v-model.trim="editableSplitSuggestion.notes" rows="3" />
                      </label>
                    </template>
                    <template v-if="activeSplitSuggestion.suggested_content_type === 'must_read'">
                      <label class="admin-form__wide">
                        <span>候选更新正文</span>
                        <textarea v-model.trim="editableSplitSuggestion.update_body" rows="5" />
                      </label>
                      <label class="admin-form__wide">
                        <span>候选调整要点</span>
                        <textarea v-model.trim="editableSplitSuggestion.adjustment_points" rows="4" />
                      </label>
                    </template>
                  </div>
                  <button class="admin-button admin-button--primary" type="button" @click="saveSplitSuggestionEdits">
                    更新候选
                  </button>
                </section>
              </div>
              <div v-if="importResult.split_suggestions.length" class="import-result__actions">
                <button
                  class="admin-button admin-button--primary"
                  type="button"
                  :disabled="!canSaveSplitDrafts"
                  @click="saveSelectedSuggestions"
                >
                  {{ isSavingSplitDrafts ? '保存中' : '保存选中为草稿' }}
                </button>
              </div>
            </div>
            <ul v-if="importWarnings.length" class="import-result__warnings">
              <li v-for="warning in importWarnings" :key="warning">
                {{ warning }}
              </li>
            </ul>
          </section>
        </section>

        <label>
          <span>分类</span>
          <input
            v-model.trim="form.category"
            type="text"
            list="content-category-options"
          />
          <datalist id="content-category-options">
            <option
              v-for="category in categorySuggestions"
              :key="category"
              :value="category"
            />
          </datalist>
        </label>
        <label>
          <span>权限级别</span>
          <select v-model="form.permission_level">
            <option value="">请选择</option>
            <option value="general">通用级</option>
            <option value="full">全量级</option>
          </select>
        </label>
        <label>
          <span>可见范围</span>
          <select v-model="form.scope_type" @change="onScopeTypeChange">
            <option value="global">全公司通用</option>
            <option value="department">限定部门</option>
          </select>
        </label>
        <label v-if="form.scope_type === 'department'">
          <span>限定部门</span>
          <select v-model.number="form.department_id">
            <option :value="null">请选择部门</option>
            <option v-for="department in departments" :key="department.id" :value="department.id">
              {{ department.name }}
            </option>
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
            <select v-model="form.scene">
              <option value="">请选择</option>
              <option v-for="scene in sceneSuggestions" :key="scene" :value="scene">
                {{ scene }}
              </option>
            </select>
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
            <textarea v-model.trim="form.adjustment_points" rows="4" placeholder="每行一个调整要点" />
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

<style scoped>
.editor-mode-switch {
  display: flex;
  gap: 8px;
}

.editor-mode-switch button,
.import-result__tabs button {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  color: #334155;
  cursor: pointer;
  padding: 8px 12px;
}

.editor-mode-switch button.active,
.import-result__tabs button.active {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #ffffff;
}

.import-panel__progress {
  display: grid;
  gap: 6px;
  margin-top: 12px;
}

.import-panel__progress-meta {
  align-items: center;
  color: #475569;
  display: flex;
  justify-content: space-between;
}

.import-panel__progress progress {
  height: 10px;
  width: 100%;
}

.import-result__candidate {
  border-top: 1px solid #e2e8f0;
  display: grid;
  gap: 8px;
  grid-template-columns: minmax(0, 1fr);
  padding: 12px 0;
}

.import-result__candidate-head {
  align-items: start;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) auto;
}

.import-result__detail-head {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.import-result__candidate-head label {
  align-items: start;
  display: flex;
  gap: 8px;
  min-width: 0;
}

.import-result__candidate-toggle {
  align-items: start;
  display: grid !important;
  gap: 8px;
  grid-template-columns: 20px minmax(0, 1fr);
  min-width: 0;
}

.import-result__candidate-toggle .import-result__candidate-checkbox {
  border-radius: 4px;
  flex: none;
  height: 18px;
  margin-top: 3px;
  min-height: 18px;
  padding: 0;
  width: 18px;
}

.import-result__candidate-title {
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.import-result__candidate-fields {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.import-result__candidate-fields label {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.import-result__candidate-status {
  border-radius: 999px;
  color: #334155;
  flex: 0 0 auto;
  font-size: 12px;
  line-height: 1;
  padding: 5px 8px;
  white-space: nowrap;
}

.import-result__candidate-status[data-status='valid'] {
  background: #dcfce7;
  color: #166534;
}

.import-result__candidate-status[data-status='warning'] {
  background: #fef3c7;
  color: #92400e;
}

.import-result__candidate-status[data-status='invalid'] {
  background: #fee2e2;
  color: #991b1b;
}

.import-result__detail {
  border-top: 1px solid #cbd5e1;
  display: grid;
  gap: 12px;
  margin-top: 12px;
  padding-top: 16px;
}

.import-result__detail h4 {
  margin: 0 0 6px;
}

.import-result__detail-head p {
  color: #475569;
  margin: 0;
  overflow-wrap: anywhere;
}

.import-result__modal-backdrop {
  align-items: center;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  inset: 0;
  justify-content: center;
  padding: 24px;
  position: fixed;
  z-index: 60;
}

.import-result__detail--modal {
  background: #ffffff;
  border: 0;
  border-radius: 8px;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.22);
  margin: 0;
  max-height: calc(100vh - 48px);
  max-width: 760px;
  overflow: auto;
  padding: 20px;
  width: min(760px, 100%);
}

.import-result__detail-preview {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #334155;
  margin: 0;
  padding: 10px;
  white-space: pre-wrap;
}

.import-result__detail-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (max-width: 640px) {
  .import-result__candidate-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
