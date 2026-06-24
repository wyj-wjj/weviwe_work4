import { apiClient } from './client'

export interface RagSource {
  content_id: number
  version_id: number
  chunk_id: number
  title: string
  content_type: string
  updated_at: string
  update_level: 'minor' | 'medium' | 'major'
  relevance_score: number
}

export interface RagAnswerResponse {
  hit: boolean
  answer: string
  sources: RagSource[]
  usage?: Record<string, unknown>
}

export async function askRag(
  question: string,
  signal?: AbortSignal,
): Promise<RagAnswerResponse> {
  const response = await apiClient.post<RagAnswerResponse>(
    '/app/rag/ask',
    { question },
    { signal, timeout: 10000 },
  )
  return response.data
}
