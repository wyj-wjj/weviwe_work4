import { apiClient } from './client'

export interface AdminMissedQuestion {
  id: number
  question: string
  user_id: number | null
  username: string | null
  account_type: 'admin' | 'full_user' | 'general_user'
  content_level: 'general' | 'full'
  asked_at: string
  status: 'new' | 'handled'
  handled_at: string | null
}

export async function listAdminMissedQuestions(status: string, page = 1, pageSize = 20) {
  const response = await apiClient.get<{
    items: AdminMissedQuestion[]
    total: number
    page: number
    page_size: number
  }>('/admin/missed-questions', {
    params: {
      page,
      page_size: pageSize,
      status: status || undefined,
    },
  })
  return response.data
}

export async function markAdminMissedQuestionHandled(questionId: number) {
  const response = await apiClient.post<AdminMissedQuestion>(
    `/admin/missed-questions/${questionId}/mark-handled`,
  )
  return response.data
}
