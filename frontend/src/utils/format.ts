export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-'
  }
  return value.replace('T', ' ').slice(0, 16)
}

export function permissionLabel(value: string): string {
  return value === 'full' ? '全量级' : '通用级'
}

export function scopeLabel(scopeType: string | null | undefined): string {
  return scopeType === 'department' ? '本部门' : '全公司通用'
}

export function adminScopeLabel(scopeType: string | null | undefined, departmentName?: string | null): string {
  if (scopeType === 'department') {
    return departmentName ? `限定部门：${departmentName}` : '限定部门'
  }
  return '全公司通用'
}

export function updateLevelLabel(value: string | null | undefined): string {
  if (value === 'minor') {
    return '小更新'
  }
  if (value === 'medium') {
    return '中更新'
  }
  if (value === 'major') {
    return '大更新'
  }
  return '-'
}

export function contentTypeLabel(value: string): string {
  if (value === 'must_read') {
    return '最新必读'
  }
  if (value === 'standard_script') {
    return '标准化话术'
  }
  return '核心基础话术'
}

export function sourceDetailPath(contentType: string, contentId: number): string {
  if (contentType === 'must_read') {
    return `/app/must-reads/${contentId}`
  }
  return `/app/scripts/${contentId}`
}
