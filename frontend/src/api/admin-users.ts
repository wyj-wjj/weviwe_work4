import { apiClient } from './client'

export interface AdminUser {
  id: number
  username: string
  display_name: string
  account_type: 'admin' | 'full_user' | 'general_user'
  content_level: 'general' | 'full'
  department_id: number | null
  department_name: string | null
  is_active: boolean
  created_at?: string
  updated_at: string
}

export interface AdminUserCreatePayload {
  username: string
  password: string
  display_name: string
  account_type: AdminUser['account_type']
  content_level: AdminUser['content_level']
  department_id?: number | null
}

export interface AdminUserUpdatePayload {
  username?: string
  display_name: string
  account_type: AdminUser['account_type']
  content_level: AdminUser['content_level']
  department_id?: number | null
  is_active: boolean
}

export async function listAdminUsers(page = 1, pageSize = 20) {
  const response = await apiClient.get<{
    items: AdminUser[]
    total: number
    page: number
    page_size: number
  }>('/admin/users', { params: { page, page_size: pageSize } })
  return response.data
}

export async function createAdminUser(payload: AdminUserCreatePayload) {
  const response = await apiClient.post<AdminUser>('/admin/users', payload)
  return response.data
}

export async function updateAdminUser(userId: number, payload: AdminUserUpdatePayload) {
  const response = await apiClient.patch<AdminUser>(`/admin/users/${userId}`, payload)
  return response.data
}

export async function resetAdminUserPassword(userId: number, password: string) {
  const response = await apiClient.post<{ reset: boolean }>(
    `/admin/users/${userId}/reset-password`,
    { password },
  )
  return response.data
}

export async function disableAdminUser(userId: number) {
  const response = await apiClient.post<AdminUser>(`/admin/users/${userId}/disable`)
  return response.data
}

export async function enableAdminUser(userId: number) {
  const response = await apiClient.post<AdminUser>(`/admin/users/${userId}/enable`)
  return response.data
}
