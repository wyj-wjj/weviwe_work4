import { fireEvent, render, waitFor } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import App from '../src/App.vue'
import { apiClient } from '../src/api/client'
import { createAppRouter } from '../src/router'
import { useAuthStore } from '../src/stores/auth'

const adminUser = {
  id: 1,
  username: 'admin',
  display_name: '管理员',
  account_type: 'admin' as const,
  content_level: 'full' as const,
}

async function renderAdmin(path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createAppRouter(createMemoryHistory())
  useAuthStore().setSession('admin-token', adminUser)
  await router.push(path)
  await router.isReady()
  return {
    router,
    ...render(App, {
      global: {
        plugins: [pinia, router],
      },
    }),
  }
}

function contentItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    content_type: 'base_script',
    title: '基础接待话术',
    category: '接待',
    permission_level: 'general',
    status: 'draft',
    current_version_id: null,
    current_version_no: null,
    index_status: 'not_synced',
    summary: '摘要',
    body: '正文',
    structured_payload: { points: ['先问候'] },
    ...overrides,
  }
}

beforeEach(() => {
  sessionStorage.clear()
  vi.restoreAllMocks()
})

test('admin content list filters, paginates, gates actions, and labels every index state', async () => {
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [
        contentItem(),
        contentItem({
          id: 2,
          title: '已发布话术',
          status: 'published',
          current_version_id: 2,
          current_version_no: 1,
          index_status: 'synced',
        }),
        contentItem({
          id: 3,
          title: '失败话术',
          status: 'published',
          current_version_id: 3,
          current_version_no: 1,
          index_status: 'failed',
        }),
        contentItem({
          id: 4,
          title: '同步中话术',
          status: 'published',
          current_version_id: 4,
          current_version_no: 1,
          index_status: 'syncing',
        }),
      ],
      total: 41,
      page: 1,
      page_size: 20,
    },
  })

  const { getByLabelText, getByRole, getByText, getAllByRole } = await renderAdmin(
    '/admin/contents',
  )

  await waitFor(() => expect(getByText('基础接待话术')).toBeInTheDocument())
  expect(getByText('未同步')).toBeInTheDocument()
  expect(getByText('已同步')).toBeInTheDocument()
  expect(getByText('同步失败')).toBeInTheDocument()
  expect(getByText('同步中')).toBeInTheDocument()
  expect(getAllByRole('link', { name: '编辑' })).toHaveLength(4)
  expect(getAllByRole('button', { name: '发布' })).toHaveLength(4)
  expect(getAllByRole('button', { name: '下线' })).toHaveLength(3)
  expect(getAllByRole('link', { name: '历史' })).toHaveLength(3)
  expect(getAllByRole('button', { name: '重试索引' })).toHaveLength(1)

  await fireEvent.update(getByLabelText('内容类型'), 'standard_script')
  await fireEvent.update(getByLabelText('内容状态'), 'published')
  await fireEvent.update(getByLabelText('权限级别'), 'full')
  await fireEvent.update(getByLabelText('分类'), '价格')
  await fireEvent.click(getByRole('button', { name: '筛选' }))

  await waitFor(() => {
    expect(get).toHaveBeenLastCalledWith('/admin/contents', {
      params: {
        category: '价格',
        content_type: 'standard_script',
        page: 1,
        page_size: 20,
        permission_level: 'full',
        status: 'published',
      },
    })
  })

  await fireEvent.click(getByRole('button', { name: '下一页' }))
  await waitFor(() => {
    expect(get).toHaveBeenLastCalledWith('/admin/contents', {
      params: expect.objectContaining({
        category: '价格',
        content_type: 'standard_script',
        page: 2,
        permission_level: 'full',
        status: 'published',
      }),
    })
  })
})

test('admin content actions confirm publish/offline, report failed indexing, and refresh retry', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [
        contentItem({
          id: 8,
          title: '待处理话术',
          content_type: 'standard_script',
          permission_level: 'full',
          status: 'published',
          current_version_id: 8,
          current_version_no: 2,
          index_status: 'failed',
        }),
      ],
      total: 1,
      page: 1,
      page_size: 20,
    },
  })
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async (url) => ({
    data: contentItem({
      id: 8,
      title: '待处理话术',
      status: url.endsWith('/offline') ? 'offline' : 'published',
      index_status: url.endsWith('/retry-index') ? 'synced' : 'failed',
    }),
  }))

  const { getByRole, getByText } = await renderAdmin('/admin/contents')
  await waitFor(() => expect(getByText('待处理话术')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '发布' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/8/publish'),
  )
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('全量级'))
  expect(getByText('内容已发布，但 AI 检索暂不可用')).toBeInTheDocument()

  await fireEvent.click(getByRole('button', { name: '重试索引' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/8/retry-index'),
  )

  await fireEvent.click(getByRole('button', { name: '下线' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/8/offline'),
  )
  expect(get.mock.calls.length).toBeGreaterThan(1)
})

test('admin content editor validates common fields and builds type-specific payloads', async () => {
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: contentItem({ id: 9, content_type: 'standard_script' }),
  })

  const { getByLabelText, getByRole, getByText, queryByLabelText } = await renderAdmin(
    '/admin/contents/new',
  )

  await fireEvent.click(getByRole('button', { name: '保存草稿' }))
  expect(getByText('请完整填写必填字段')).toBeInTheDocument()
  expect(post).not.toHaveBeenCalled()

  await fireEvent.update(getByLabelText('标题'), '价格异议话术')
  await fireEvent.update(getByLabelText('内容类型'), 'must_read')
  expect(getByLabelText('更新正文')).toBeInTheDocument()
  expect(getByLabelText('调整要点')).toBeInTheDocument()
  expect(queryByLabelText('场景')).not.toBeInTheDocument()

  await fireEvent.update(getByLabelText('内容类型'), 'standard_script')
  await fireEvent.update(getByLabelText('分类'), '价格')
  await fireEvent.update(getByLabelText('权限级别'), 'full')
  await fireEvent.update(getByLabelText('摘要'), '价格沟通摘要')
  await fireEvent.update(getByLabelText('正文'), '先解释价值。')
  expect(getByLabelText('场景')).toBeInTheDocument()
  expect(getByLabelText('推荐说法')).toBeInTheDocument()
  expect(getByLabelText('禁用说法')).toBeInTheDocument()
  expect(getByLabelText('注意事项')).toBeInTheDocument()
  await fireEvent.update(getByLabelText('场景'), '价格异议')
  await fireEvent.update(getByLabelText('推荐说法'), '先解释价值，再确认预算。')
  await fireEvent.update(getByLabelText('禁用说法'), '不要直接降价。')
  await fireEvent.update(getByLabelText('注意事项'), '保持专业。')
  await fireEvent.click(getByRole('button', { name: '保存草稿' }))

  await waitFor(() => {
    expect(post).toHaveBeenCalledWith('/admin/contents', {
      body: '先解释价值。',
      category: '价格',
      content_type: 'standard_script',
      permission_level: 'full',
      structured_payload: {
        forbidden_speech: '不要直接降价。',
        notes: '保持专业。',
        recommended_speech: '先解释价值，再确认预算。',
        scene: '价格异议',
      },
      summary: '价格沟通摘要',
      title: '价格异议话术',
    })
  })
})

test('admin content history renders version snapshot and publisher', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [
        {
          id: 11,
          version_no: 2,
          title: '第二版口径',
          summary: '摘要',
          body: '第二版正文',
          structured_payload: null,
          published_at: '2026-06-18T09:00:00',
          effective_at: '2026-06-18T09:00:00',
          expired_at: null,
          created_by: 1,
          created_by_name: '管理员',
          permission_level: 'full',
        },
      ],
    },
  })

  const { getByText } = await renderAdmin('/admin/contents/11/versions')

  await waitFor(() => expect(getByText('第二版口径')).toBeInTheDocument())
  expect(getByText('版本 2')).toBeInTheDocument()
  expect(getByText('发布人：管理员')).toBeInTheDocument()
  expect(getByText('全量级')).toBeInTheDocument()
  expect(getByText('第二版正文')).toBeInTheDocument()
})
