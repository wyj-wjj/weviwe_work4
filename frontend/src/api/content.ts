import { apiClient } from './client'

export interface MustReadItem {
  id: number
  title: string
  published_at: string
  effective_at: string
  permission_level: 'general' | 'full'
  update_body: string
  adjustment_points: string[]
}

export interface MustReadListResponse {
  items: MustReadItem[]
}

export interface BaseScriptItem {
  id: number
  content_type: 'base_script'
  title: string
  category: string | null
  permission_level: 'general' | 'full'
  updated_at: string
  summary_points: string[]
}

export interface StandardScriptItem {
  id: number
  content_type: 'standard_script'
  title: string
  category: string | null
  permission_level: 'general' | 'full'
  updated_at: string
  scene: string | null
  recommended_speech_summary: string
}

export type ScriptListItem = BaseScriptItem | StandardScriptItem

export interface ScriptListResponse {
  base_scripts: BaseScriptItem[]
  standard_scripts: StandardScriptItem[]
}

export interface BaseScriptDetail extends BaseScriptItem {
  body: string
  copy_text: string
}

export interface StandardScriptDetail extends Omit<StandardScriptItem, 'recommended_speech_summary'> {
  recommended_speech: string | null
  forbidden_speech: string | null
  notes: string | null
  copy_text: string
}

export type ScriptDetail = BaseScriptDetail | StandardScriptDetail

export async function listMustReads(): Promise<MustReadListResponse> {
  const response = await apiClient.get<MustReadListResponse>('/app/must-reads')
  return response.data
}

export async function getMustRead(contentId: number | string): Promise<MustReadItem> {
  const response = await apiClient.get<MustReadItem>(`/app/must-reads/${contentId}`)
  return response.data
}

export async function listScripts(params: { category?: string } = {}): Promise<ScriptListResponse> {
  const response = await apiClient.get<ScriptListResponse>('/app/scripts', {
    params: params.category ? { category: params.category } : undefined,
  })
  return response.data
}

export async function getScript(contentId: number | string): Promise<ScriptDetail> {
  const response = await apiClient.get<ScriptDetail>(`/app/scripts/${contentId}`)
  return response.data
}
