export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-'
  }
  const trimmed = value.trim()
  if (!trimmed) {
    return '-'
  }
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed)
  const normalized = hasTimezone ? trimmed : `${trimmed}Z`
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) {
    return '-'
  }
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}`
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
