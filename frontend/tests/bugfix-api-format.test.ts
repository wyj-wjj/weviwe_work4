import { listAdminContentCategories } from '../src/api/admin-content'
import { apiClient } from '../src/api/client'
import { getQuiz } from '../src/api/quiz'
import { formatDateTime } from '../src/utils/format'

beforeEach(() => {
  vi.restoreAllMocks()
})

test('formatDateTime renders UTC input as Beijing time and hides invalid values', () => {
  expect(formatDateTime('2026-06-29T10:30:00Z')).toBe('2026-06-29 18:30')
  expect(formatDateTime('2026-06-29T10:30:00')).toBe('2026-06-29 18:30')
  expect(formatDateTime('')).toBe('-')
  expect(formatDateTime('not-a-date')).toBe('-')
})

test('admin content category suggestions use the dedicated endpoint', async () => {
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: { items: ['回款催收'] },
  })

  await expect(listAdminContentCategories()).resolves.toEqual({ items: ['回款催收'] })
  expect(get).toHaveBeenCalledWith('/admin/content-categories')
})

test('employee quiz request sends mode and optional category as query params', async () => {
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: { items: [] },
  })

  await getQuiz({ mode: 'review', category: '价格口径' })

  expect(get).toHaveBeenCalledWith('/app/quiz', {
    params: { mode: 'review', category: '价格口径' },
  })
})
