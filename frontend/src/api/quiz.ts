import { apiClient } from './client'

export type QuizRelatedContentType = 'base_script' | 'standard_script' | 'must_read'

export interface QuizQuestion {
  id: number
  question: string
  options: Array<string | { label?: string; value?: string }>
  explanation: string | null
  related_content_id: number | null
  related_content_type: QuizRelatedContentType | null
  related_content_category?: string | null
  permission_level: 'general' | 'full'
  status: string
}

export interface QuizResponse {
  items: QuizQuestion[]
}

export interface QuizSubmitPayload {
  answers: Array<{
    question_id: number
    selected_answer: string
  }>
}

export interface QuizSubmitResult {
  question_id: number
  selected_answer: string
  is_correct: boolean
  correct_answer: string
  explanation: string | null
  related_content_id: number | null
  related_content_type: QuizRelatedContentType | null
}

export interface QuizSubmitResponse {
  results: QuizSubmitResult[]
}

export interface QuizRequestParams {
  mode?: 'latest' | 'review'
  category?: string
  refresh_seed?: string | number
}

export async function getQuiz(params: QuizRequestParams = {}): Promise<QuizResponse> {
  const requestParams: QuizRequestParams = {}
  if (params.mode) {
    requestParams.mode = params.mode
  }
  if (params.category) {
    requestParams.category = params.category
  }
  if (params.refresh_seed !== undefined && params.refresh_seed !== '') {
    requestParams.refresh_seed = params.refresh_seed
  }
  if (Object.keys(requestParams).length === 0) {
    const response = await apiClient.get<QuizResponse>('/app/quiz')
    return response.data
  }
  const response = await apiClient.get<QuizResponse>('/app/quiz', { params: requestParams })
  return response.data
}

export async function submitQuiz(payload: QuizSubmitPayload): Promise<QuizSubmitResponse> {
  const response = await apiClient.post<QuizSubmitResponse>('/app/quiz/submit', payload)
  return response.data
}
