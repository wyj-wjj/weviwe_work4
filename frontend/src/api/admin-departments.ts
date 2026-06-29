import { apiClient } from './client'

export interface Department {
  id: number
  name: string
  code: string
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface DepartmentPayload {
  name: string
  code: string
}

export async function listAdminDepartments(includeInactive = true) {
  const response = await apiClient.get<{
    items: Department[]
    total: number
    page: number
    page_size: number
  }>('/admin/departments', { params: { include_inactive: includeInactive } })
  return response.data
}

export async function createAdminDepartment(payload: DepartmentPayload) {
  const response = await apiClient.post<Department>('/admin/departments', payload)
  return response.data
}

export async function updateAdminDepartment(departmentId: number, payload: Partial<DepartmentPayload>) {
  const response = await apiClient.patch<Department>(`/admin/departments/${departmentId}`, payload)
  return response.data
}

export async function disableAdminDepartment(departmentId: number) {
  const response = await apiClient.post<Department>(`/admin/departments/${departmentId}/disable`)
  return response.data
}

export async function enableAdminDepartment(departmentId: number) {
  const response = await apiClient.post<Department>(`/admin/departments/${departmentId}/enable`)
  return response.data
}
