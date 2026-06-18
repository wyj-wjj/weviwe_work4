import { apiClient } from './client'

export type QuizRelatedContentType = 'base_script' | 'standard_script' | 'must_read'

export interface QuizQuestion {
  id: number
  question: string
  options: Array<string | { label?: string; value?: string }>
  explanation: string | null
  related_content_id: number | null
  related_content_type: QuizRelatedContentType | null
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

export async function getQuiz(): Promise<QuizResponse> {
  const response = await apiClient.get<QuizResponse>('/app/quiz')
  return response.data
}

export async function submitQuiz(payload: QuizSubmitPayload): Promise<QuizSubmitResponse> {
  const response = await apiClient.post<QuizSubmitResponse>('/app/quiz/submit', payload)
  return response.data
}
