import { apiClient } from './client'

export interface AdminQuizQuestion {
  id: number
  question: string
  options: Array<string | { label?: string; value?: string }>
  answer: string
  explanation: string | null
  related_content_id: number | null
  related_version_id: number | null
  related_content_title: string | null
  permission_level: 'general' | 'full'
  status: 'enabled' | 'disabled'
  source_type: 'manual' | 'ai_generated' | 'ai_assisted'
  review_status: 'draft' | 'pending_review' | 'approved' | 'rejected'
  generation_batch_id: number | null
  needs_review: boolean
  review_reason: string | null
  expires_at: string | null
  priority: number
  source_valid: boolean
  source_invalid_reason:
    | 'source_content_missing'
    | 'source_content_offline'
    | 'source_content_inactive'
    | 'source_content_no_current_version'
    | 'source_version_stale'
    | 'quiz_set_inactive'
    | null
  updated_at: string
}

export interface AdminQuizPayload {
  question: string
  options: string[]
  answer: string
  explanation: string | null
  related_content_id: number | null
  related_version_id: number | null
  permission_level: AdminQuizQuestion['permission_level']
  status: AdminQuizQuestion['status']
  source_type: AdminQuizQuestion['source_type']
  review_status: AdminQuizQuestion['review_status']
  generation_batch_id?: number | null
  needs_review: boolean
  review_reason: string | null
  expires_at?: string | null
  priority?: number
}

export interface AdminQuizGenerationBatch {
  id: number
  content_id: number
  version_id: number
  update_level: 'minor' | 'medium' | 'major'
  status: 'pending' | 'completed' | 'failed'
  model_name: string
  prompt_version: string
  requested_count: number
  generated_count: number
  created_by: number
  created_at: string
  error_message: string | null
}

export interface AdminQuizSet {
  id: number
  title: string
  description: string | null
  related_content_id: number
  related_version_id: number
  update_level: 'minor' | 'medium' | 'major'
  permission_level: AdminQuizQuestion['permission_level']
  status: 'active' | 'inactive'
  expires_at: string | null
  created_at: string
  question_count: number
}

export interface AdminQuizGeneratePayload {
  requested_count?: number | null
  create_quiz_set?: boolean
}

export async function listAdminQuizQuestions(page = 1, pageSize = 20) {
  const response = await apiClient.get<{
    items: AdminQuizQuestion[]
    total: number
    page: number
    page_size: number
  }>('/admin/quiz-questions', { params: { page, page_size: pageSize } })
  return response.data
}

export async function createAdminQuizQuestion(payload: AdminQuizPayload) {
  const response = await apiClient.post<AdminQuizQuestion>('/admin/quiz-questions', payload)
  return response.data
}

export async function updateAdminQuizQuestion(questionId: number, payload: AdminQuizPayload) {
  const response = await apiClient.patch<AdminQuizQuestion>(
    `/admin/quiz-questions/${questionId}`,
    payload,
  )
  return response.data
}

export async function setAdminQuizQuestionStatus(
  questionId: number,
  status: AdminQuizQuestion['status'],
) {
  const action = status === 'enabled' ? 'enable' : 'disable'
  const response = await apiClient.post<AdminQuizQuestion>(
    `/admin/quiz-questions/${questionId}/${action}`,
  )
  return response.data
}

export async function reviewAdminQuizQuestion(
  questionId: number,
  action: 'approve' | 'reject',
) {
  const response = await apiClient.post<AdminQuizQuestion>(
    `/admin/quiz-questions/${questionId}/${action}`,
  )
  return response.data
}

export async function listAdminQuizGenerationBatches(page = 1, pageSize = 20) {
  const response = await apiClient.get<{
    items: AdminQuizGenerationBatch[]
    total: number
    page: number
    page_size: number
  }>('/admin/quiz-generation-batches', { params: { page, page_size: pageSize } })
  return response.data
}

export async function listAdminQuizSets(page = 1, pageSize = 20) {
  const response = await apiClient.get<{
    items: AdminQuizSet[]
    total: number
    page: number
    page_size: number
  }>('/admin/quiz-sets', { params: { page, page_size: pageSize } })
  return response.data
}

export async function generateAdminQuizForContentVersion(
  contentId: number,
  versionId: number,
  payload?: AdminQuizGeneratePayload,
) {
  const endpoint = `/admin/contents/${contentId}/versions/${versionId}/generate-quiz`
  const response = payload
    ? await apiClient.post<AdminQuizGenerationBatch>(endpoint, payload)
    : await apiClient.post<AdminQuizGenerationBatch>(endpoint)
  return response.data
}
