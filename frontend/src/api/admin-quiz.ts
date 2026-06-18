import { apiClient } from './client'

export interface AdminQuizQuestion {
  id: number
  question: string
  options: Array<string | { label?: string; value?: string }>
  answer: string
  explanation: string | null
  related_content_id: number | null
  related_content_title: string | null
  permission_level: 'general' | 'full'
  status: 'enabled' | 'disabled'
  updated_at: string
}

export interface AdminQuizPayload {
  question: string
  options: string[]
  answer: string
  explanation: string | null
  related_content_id: number | null
  permission_level: AdminQuizQuestion['permission_level']
  status: AdminQuizQuestion['status']
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
