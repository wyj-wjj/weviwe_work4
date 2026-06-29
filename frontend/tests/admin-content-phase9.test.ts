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
    current_update_level: null,
    index_status: 'not_synced',
    summary: '摘要',
    body: '正文',
    structured_payload: { points: ['先问候'] },
    ...overrides,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

beforeEach(() => {
  sessionStorage.clear()
  vi.restoreAllMocks()
})

test('admin content list filters, paginates, gates actions, and labels every index state', async () => {
  const get = vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url === '/admin/content-categories') {
      return {
        data: {
          items: ['回款催收'],
        },
      }
    }
    return {
      data: {
        items: [
          contentItem(),
          contentItem({
            id: 2,
            title: '已发布话术',
            status: 'published',
            current_version_id: 2,
            current_version_no: 1,
            current_update_level: 'medium',
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
    }
  })

  const { container, getByLabelText, getByRole, getByText, getAllByRole } = await renderAdmin(
    '/admin/contents',
  )

  await waitFor(() => expect(getByText('基础接待话术')).toBeInTheDocument())
  expect(getByText('未同步')).toBeInTheDocument()
  expect(getByText('已同步')).toBeInTheDocument()
  expect(getByText('中更新')).toBeInTheDocument()
  expect(getByText('同步失败')).toBeInTheDocument()
  expect(getByText('同步中')).toBeInTheDocument()
  expect(getAllByRole('link', { name: '编辑' })).toHaveLength(4)
  expect(getAllByRole('button', { name: '发布' })).toHaveLength(4)
  expect(getAllByRole('button', { name: '下线' })).toHaveLength(3)
  expect(getAllByRole('link', { name: '历史' })).toHaveLength(3)
  expect(getAllByRole('button', { name: '重试索引' })).toHaveLength(1)
  const categoryInput = getByLabelText('分类')
  const categoryOptions = Array.from(
    container.querySelectorAll('#admin-content-filter-category-options option'),
  ).map((option) => option.getAttribute('value'))
  expect(categoryInput).toHaveAttribute('list', 'admin-content-filter-category-options')
  expect(categoryOptions).toContain('价格口径')
  expect(categoryOptions).toContain('回款催收')

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
  vi.spyOn(window, 'prompt')
    .mockReturnValueOnce('major')
    .mockReturnValueOnce('关键规则变更')
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
      current_version_id: 8,
      current_version_no: 2,
      index_status: url.endsWith('/retry-index') ? 'synced' : 'failed',
    }),
  }))

  const { getByRole, getByText } = await renderAdmin('/admin/contents')
  await waitFor(() => expect(getByText('待处理话术')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '发布' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/8/publish', {
      update_level: 'major',
      change_summary: '关键规则变更',
    }),
  )
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('全量级'))
  expect(getByText('内容已发布，但 AI 检索暂不可用')).toBeInTheDocument()
  await waitFor(() => expect(getByRole('button', { name: '发布' })).toBeEnabled())

  await fireEvent.click(getByRole('button', { name: '重试索引' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/8/retry-index'),
  )
  await waitFor(() => expect(getByRole('button', { name: '重试索引' })).toBeEnabled())

  await fireEvent.click(getByRole('button', { name: '下线' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/8/offline'),
  )
  expect(get.mock.calls.length).toBeGreaterThan(1)
})

test('publish response must confirm published status before reporting success', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  vi.spyOn(window, 'prompt')
    .mockReturnValueOnce('medium')
    .mockReturnValueOnce('局部规则变更')
  vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [
        contentItem({
          id: 8,
          title: '异常发布话术',
          status: 'draft',
          current_version_id: null,
          current_version_no: null,
          index_status: 'not_synced',
        }),
      ],
      total: 1,
      page: 1,
      page_size: 20,
    },
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: contentItem({
      id: 8,
      title: '异常发布话术',
      status: 'draft',
      current_version_id: null,
      current_version_no: null,
      index_status: 'not_synced',
    }),
  })

  const { getByRole, getByText, queryByText } = await renderAdmin('/admin/contents')
  await waitFor(() => expect(getByText('异常发布话术')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '发布' }))

  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/8/publish', {
      update_level: 'medium',
      change_summary: '局部规则变更',
    }),
  )
  expect(getByText('发布未完成，请刷新后确认内容状态')).toBeInTheDocument()
  expect(queryByText('内容发布成功')).not.toBeInTheDocument()
})

test('publish success with pending quiz generation gives a non-failure follow-up message', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  vi.spyOn(window, 'prompt')
    .mockReturnValueOnce('major')
    .mockReturnValueOnce('新增关键口径')
  vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [
        contentItem({
          id: 8,
          title: '大更新内容',
          status: 'draft',
          current_version_id: null,
          current_version_no: null,
          index_status: 'not_synced',
        }),
      ],
      total: 1,
      page: 1,
      page_size: 20,
    },
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: contentItem({
      id: 8,
      title: '大更新内容',
      status: 'published',
      current_version_id: 88,
      current_version_no: 1,
      index_status: 'synced',
      quiz_generation_status: 'pending',
    }),
  })

  const { getByRole, getByText, queryByText } = await renderAdmin('/admin/contents')
  await waitFor(() => expect(getByText('大更新内容')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '发布' }))

  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/8/publish', {
      update_level: 'major',
      change_summary: '新增关键口径',
    }),
  )
  expect(getByText('内容已发布；AI 候选题可在历史版本页生成')).toBeInTheDocument()
  expect(queryByText('发布失败，请稍后重试')).not.toBeInTheDocument()
})

test('publish pending prevents duplicate requests and disables every mutation for the same content', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  vi.spyOn(window, 'prompt')
    .mockReturnValueOnce('minor')
    .mockReturnValueOnce('修正错别字')
  vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [
        contentItem({
          id: 8,
          status: 'published',
          current_version_id: 8,
          current_version_no: 1,
          index_status: 'failed',
        }),
      ],
      total: 1,
      page: 1,
      page_size: 20,
    },
  })
  const pending = deferred<{ data: ReturnType<typeof contentItem> }>()
  const post = vi.spyOn(apiClient, 'post').mockReturnValue(pending.promise)

  const { getByRole, getByText } = await renderAdmin('/admin/contents')
  await waitFor(() => expect(getByText('基础接待话术')).toBeInTheDocument())

  const publishButton = getByRole('button', { name: '发布' })
  await fireEvent.click(publishButton)
  await fireEvent.click(publishButton)

  expect(post).toHaveBeenCalledTimes(1)
  expect(post).toHaveBeenCalledWith('/admin/contents/8/publish', {
    update_level: 'minor',
    change_summary: '修正错别字',
  })
  expect(getByRole('button', { name: '发布中' })).toBeDisabled()
  expect(getByRole('button', { name: '下线' })).toBeDisabled()
  expect(getByRole('button', { name: '重试索引' })).toBeDisabled()

  pending.resolve({
    data: contentItem({
      id: 8,
      status: 'published',
      current_version_id: 8,
      current_version_no: 1,
      index_status: 'synced',
    }),
  })
  await waitFor(() => expect(getByRole('button', { name: '发布' })).toBeEnabled())
})

test.each([
  ['下线', '/admin/contents/8/offline', '下线中'],
  ['重试索引', '/admin/contents/8/retry-index', '重试中'],
] as const)(
  '%s pending disables all same-content mutations',
  async (actionName, endpoint, pendingLabel) => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: {
        items: [
          contentItem({
            id: 8,
            status: 'published',
            current_version_id: 8,
            current_version_no: 1,
            index_status: 'failed',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    const pending = deferred<{ data: ReturnType<typeof contentItem> }>()
    const post = vi.spyOn(apiClient, 'post').mockReturnValue(pending.promise)

    const { getByRole, getByText } = await renderAdmin('/admin/contents')
    await waitFor(() => expect(getByText('基础接待话术')).toBeInTheDocument())

    await fireEvent.click(getByRole('button', { name: actionName }))

    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith(endpoint)
    expect(getByRole('button', { name: pendingLabel })).toBeDisabled()
    expect(getByRole('button', { name: '发布' })).toBeDisabled()
    for (const button of [
      getByRole('button', { name: pendingLabel }),
      getByRole('button', {
        name: actionName === '下线' ? '重试索引' : '下线',
      }),
    ]) {
      expect(button).toBeDisabled()
    }

    pending.resolve({
      data: contentItem({
        id: 8,
        status: 'published',
        current_version_id: 8,
        current_version_no: 1,
        index_status: 'synced',
      }),
    })
    await waitFor(() => expect(getByRole('button', { name: actionName })).toBeEnabled())
  },
)

test('canceling publish or offline confirmation has no API side effects', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(false)
  vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [
        contentItem({
          id: 8,
          status: 'published',
          current_version_id: 8,
          current_version_no: 1,
          index_status: 'synced',
        }),
      ],
      total: 1,
      page: 1,
      page_size: 20,
    },
  })
  const post = vi.spyOn(apiClient, 'post')

  const { getByRole, getByText } = await renderAdmin('/admin/contents')
  await waitFor(() => expect(getByText('基础接待话术')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '发布' }))
  await fireEvent.click(getByRole('button', { name: '下线' }))

  expect(window.confirm).toHaveBeenCalledTimes(2)
  expect(post).not.toHaveBeenCalled()
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
          update_level: 'major',
          change_summary: '关键规则变更',
          quiz_action: 'generate_pack',
          ai_suggested_update_level: null,
          ai_suggestion_reason: null,
        },
      ],
    },
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: {
      id: 7,
      content_id: 11,
      version_id: 11,
      update_level: 'major',
      status: 'completed',
      model_name: 'qwen-plus',
      prompt_version: 'quiz-generation-v1',
      requested_count: 5,
      generated_count: 3,
      created_by: 1,
      created_at: '2026-06-18T09:05:00',
      error_message: null,
    },
  })

  const { getByRole, getByText } = await renderAdmin('/admin/contents/11/versions')

  await waitFor(() => expect(getByText('第二版口径')).toBeInTheDocument())
  expect(getByText('版本 2')).toBeInTheDocument()
  expect(getByText('发布人：管理员')).toBeInTheDocument()
  expect(getByText('全量级')).toBeInTheDocument()
  expect(getByText('更新级别：大更新')).toBeInTheDocument()
  expect(getByText('题库动作：建议生成专题候选题')).toBeInTheDocument()
  expect(getByText('变更摘要：关键规则变更')).toBeInTheDocument()
  expect(getByText('第二版正文')).toBeInTheDocument()

  await fireEvent.click(getByRole('button', { name: '生成候选题' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/11/versions/11/generate-quiz', {
      create_quiz_set: true,
    }),
  )
  expect(getByText('已生成 3 道候选题，批次 ID：7')).toBeInTheDocument()
})
