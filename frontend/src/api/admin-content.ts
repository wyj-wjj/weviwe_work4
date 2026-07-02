import { apiClient } from './client'

export const CONTENT_IMPORT_TIMEOUT_MS = 120000

export interface AdminContent {
  id: number
  content_type: 'base_script' | 'standard_script' | 'must_read'
  title: string
  category: string | null
  permission_level: 'general' | 'full'
  scope_type?: 'global' | 'department'
  department_id?: number | null
  department_name?: string | null
  status: 'draft' | 'published' | 'offline'
  current_version_id: number | null
  current_version_no: number | null
  current_update_level: ContentUpdateLevel | null
  index_status: 'not_synced' | 'syncing' | 'synced' | 'failed'
  summary: string | null
  body: string
  structured_payload: Record<string, unknown> | null
  quiz_generation_status?: 'not_required' | 'pending' | 'completed' | 'failed'
}

export interface AdminContentPayload {
  content_type: AdminContent['content_type']
  title: string
  category: string
  permission_level: AdminContent['permission_level']
  scope_type?: AdminContent['scope_type']
  department_id?: number | null
  summary: string
  body: string
  structured_payload: Record<string, unknown>
}

export type ContentImportParseMode = 'fast' | 'enhanced'

export interface ContentImportDraft {
  title: string
  category: string | null
  summary: string
  body: string
  structured_payload: Record<string, unknown>
  warnings: string[]
}

export interface ContentImportSplitSuggestion extends ContentImportDraft {
  temp_id: string
  suggested_content_type: AdminContent['content_type']
  source_span: {
    start_block: number
    end_block: number
  }
  confidence: 'low' | 'medium' | 'high'
  validation_status?: 'valid' | 'invalid' | 'warning'
  is_saveable?: boolean
  missing_fields?: string[]
  quality_warnings?: string[]
}

export interface ContentImportResult {
  content_type: AdminContent['content_type']
  single_draft: ContentImportDraft
  split_suggestions: ContentImportSplitSuggestion[]
  raw_text: string
  parse_method: string
  warnings: string[]
  extraction_warnings?: string[]
  structure_warnings?: string[]
  structure_status?: 'completed' | 'failed'
  structure_error_code?: string | null
  structure_error_message?: string | null
  parse_trace?: {
    file_type: 'docx' | 'pdf'
    parse_method: string
    local_block_count: number
    image_count: number
    ocr_image_count: number
    ocr_failed_count: number
    ocr_page_count: number
    structure_status?: 'completed' | 'failed' | null
  } | null
  pages: Array<{
    page: number
    chosen: 'local' | 'ocr'
    local_score: number
    ocr_score: number
    warning: string | null
  }>
}

export interface AdminContentFilters {
  content_type?: string
  status?: string
  permission_level?: string
  category?: string
  page: number
  page_size: number
}

export type ContentUpdateLevel = 'minor' | 'medium' | 'major'
export type ContentQuizAction = 'none' | 'review_related' | 'generate_pack'

export interface AdminContentPublishPayload {
  update_level: ContentUpdateLevel
  change_summary?: string | null
  quiz_action?: ContentQuizAction | null
  ai_suggested_update_level?: ContentUpdateLevel | null
  ai_suggestion_reason?: string | null
}

export interface AdminContentVersion {
  id: number
  version_no: number
  title: string
  summary: string | null
  body: string
  structured_payload: Record<string, unknown> | null
  published_at: string | null
  effective_at: string | null
  expired_at: string | null
  created_by: number
  created_by_name: string | null
  permission_level: 'general' | 'full'
  scope_type?: 'global' | 'department'
  department_id?: number | null
  department_name?: string | null
  update_level: ContentUpdateLevel
  change_summary: string | null
  quiz_action: ContentQuizAction
  ai_suggested_update_level: ContentUpdateLevel | null
  ai_suggestion_reason: string | null
}

export async function listAdminContents(params: AdminContentFilters) {
  const response = await apiClient.get<{
    items: AdminContent[]
    total: number
    page: number
    page_size: number
  }>('/admin/contents', { params })
  return response.data
}

export async function listAdminContentCategories() {
  const response = await apiClient.get<{ items: string[] }>('/admin/content-categories')
  return response.data
}

export async function listAdminContentScenes() {
  const response = await apiClient.get<{ items: string[] }>('/admin/content-scenes')
  return response.data
}

export async function parseAdminContentImport(payload: {
  content_type: AdminContent['content_type']
  parse_mode: ContentImportParseMode
  force_ocr: boolean
  file: File
}) {
  const formData = new FormData()
  formData.append('content_type', payload.content_type)
  formData.append('parse_mode', payload.parse_mode)
  formData.append('force_ocr', String(payload.force_ocr))
  formData.append('file', payload.file)
  const response = await apiClient.post<ContentImportResult>('/admin/content-import/parse', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: CONTENT_IMPORT_TIMEOUT_MS,
  })
  return response.data
}

export async function getAdminContent(contentId: number) {
  const response = await apiClient.get<AdminContent>(`/admin/contents/${contentId}`)
  return response.data
}

export async function createAdminContent(payload: AdminContentPayload) {
  const response = await apiClient.post<AdminContent>('/admin/contents', payload)
  return response.data
}

export async function updateAdminContent(
  contentId: number,
  payload: Omit<AdminContentPayload, 'content_type'>,
) {
  const response = await apiClient.patch<AdminContent>(`/admin/contents/${contentId}`, payload)
  return response.data
}

export async function deleteAdminContentDraft(contentId: number) {
  await apiClient.delete(`/admin/contents/${contentId}`)
}

export async function publishAdminContent(contentId: number, payload?: AdminContentPublishPayload) {
  const endpoint = `/admin/contents/${contentId}/publish`
  const response = payload
    ? await apiClient.post<AdminContent>(endpoint, payload)
    : await apiClient.post<AdminContent>(endpoint)
  return response.data
}

export async function offlineAdminContent(contentId: number) {
  const response = await apiClient.post<AdminContent>(`/admin/contents/${contentId}/offline`)
  return response.data
}

export async function retryAdminContentIndex(contentId: number) {
  const response = await apiClient.post<AdminContent>(`/admin/contents/${contentId}/retry-index`)
  return response.data
}

export async function listAdminContentVersions(contentId: number) {
  const response = await apiClient.get<{ items: AdminContentVersion[] }>(
    `/admin/contents/${contentId}/versions`,
  )
  return response.data
}
