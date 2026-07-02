import { fireEvent, render, waitFor, within } from '@testing-library/vue'
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

async function submitPublishDialog(
  controls: Pick<Awaited<ReturnType<typeof renderAdmin>>, 'getByLabelText' | 'getByRole'>,
  updateLevel: string,
  summary: string,
) {
  await fireEvent.update(controls.getByLabelText('更新级别'), updateLevel)
  await fireEvent.update(controls.getByLabelText('变更摘要'), summary)
  await fireEvent.click(controls.getByRole('button', { name: '确认发布' }))
}

beforeEach(() => {
  sessionStorage.clear()
  vi.restoreAllMocks()
  vi.useRealTimers()
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

  const controls = await renderAdmin('/admin/contents')
  const { getByRole, getByText } = controls
  await waitFor(() => expect(getByText('待处理话术')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '发布' }))
  await submitPublishDialog(controls, 'major', '关键规则变更')
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/8/publish', {
      update_level: 'major',
      change_summary: '关键规则变更',
    }),
  )
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

  const controls = await renderAdmin('/admin/contents')
  const { getByRole, getByText, queryByText } = controls
  await waitFor(() => expect(getByText('异常发布话术')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '发布' }))
  await submitPublishDialog(controls, 'medium', '局部规则变更')

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

  const controls = await renderAdmin('/admin/contents')
  const { getByRole, getByText, queryByText } = controls
  await waitFor(() => expect(getByText('大更新内容')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '发布' }))
  await submitPublishDialog(controls, 'major', '新增关键口径')

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

  const controls = await renderAdmin('/admin/contents')
  const { getByRole, getByText, getAllByRole } = controls
  await waitFor(() => expect(getByText('基础接待话术')).toBeInTheDocument())

  const publishButton = getByRole('button', { name: '发布' })
  await fireEvent.click(publishButton)
  const dialog = getByRole('dialog', { name: '发布内容' })
  await fireEvent.update(controls.getByLabelText('更新级别'), 'minor')
  await fireEvent.update(controls.getByLabelText('变更摘要'), '修正错别字')
  const confirmButton = within(dialog).getByRole('button', { name: '确认发布' })
  await fireEvent.click(confirmButton)
  await fireEvent.click(confirmButton)

  expect(post).toHaveBeenCalledTimes(1)
  expect(post).toHaveBeenCalledWith('/admin/contents/8/publish', {
    update_level: 'minor',
    change_summary: '修正错别字',
  })
  for (const button of getAllByRole('button', { name: '发布中' })) {
    expect(button).toBeDisabled()
  }
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
  await fireEvent.click(
    within(getByRole('dialog', { name: '发布内容' })).getAllByRole('button', { name: '取消' })[0],
  )
  await fireEvent.click(getByRole('button', { name: '下线' }))

  expect(window.confirm).toHaveBeenCalledTimes(1)
  expect(post).not.toHaveBeenCalled()
})

test('admin content list deletes never published drafts after confirmation', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [contentItem({ id: 15, title: '待删除草稿', status: 'draft' })],
      total: 1,
      page: 1,
      page_size: 20,
    },
  })
  const remove = vi.spyOn(apiClient, 'delete').mockResolvedValue({ data: {} })

  const { getByRole, getByText } = await renderAdmin('/admin/contents')
  await waitFor(() => expect(getByText('待删除草稿')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '删除草稿' }))

  await waitFor(() => expect(remove).toHaveBeenCalledWith('/admin/contents/15'))
  expect(window.confirm).toHaveBeenCalledWith('确定删除这个草稿吗？删除后不可恢复。')
  expect(getByText('草稿已删除')).toBeInTheDocument()
  expect(get.mock.calls.filter(([url]) => url === '/admin/contents')).toHaveLength(2)
})

test('admin content publish uses an in-page dialog instead of chained browser prompts', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const prompt = vi.spyOn(window, 'prompt').mockReturnValue('major')
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url === '/admin/content-categories') {
      return { data: { items: [] } }
    }
    return {
      data: {
        items: [contentItem({ id: 22, title: '待发布草稿', status: 'draft' })],
        total: 1,
        page: 1,
        page_size: 20,
      },
    }
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: contentItem({
      id: 22,
      title: '待发布草稿',
      status: 'published',
      current_version_id: 220,
      current_version_no: 1,
      index_status: 'synced',
    }),
  })

  const { getByLabelText, getByRole, getByText, queryByText } = await renderAdmin('/admin/contents')
  await waitFor(() => expect(getByText('待发布草稿')).toBeInTheDocument())

  await fireEvent.click(getByRole('button', { name: '发布' }))

  const dialog = getByRole('dialog', { name: '发布内容' })
  expect(dialog).toBeInTheDocument()
  expect(within(dialog).getByText('待发布草稿')).toBeInTheDocument()
  expect(prompt).not.toHaveBeenCalled()
  expect(window.confirm).not.toHaveBeenCalled()
  expect(post).not.toHaveBeenCalled()

  await fireEvent.update(getByLabelText('更新级别'), 'medium')
  await fireEvent.update(getByLabelText('变更摘要'), '拆分导入后发布')
  await fireEvent.click(within(dialog).getByRole('button', { name: '确认发布' }))

  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents/22/publish', {
      update_level: 'medium',
      change_summary: '拆分导入后发布',
    }),
  )
  expect(getByText('内容发布成功')).toBeInTheDocument()
  expect(queryByText('发布内容')).not.toBeInTheDocument()
})

test('admin content editor validates common fields and builds type-specific payloads', async () => {
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url === '/admin/content-categories') {
      return { data: { items: [] } }
    }
    if (url === '/admin/content-scenes') {
      return { data: { items: ['价格异议'] } }
    }
    if (url === '/admin/departments') {
      return { data: { items: [] } }
    }
    return { data: {} }
  })
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
  await fireEvent.update(getByLabelText('分类'), '价格口径')
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
      category: '价格口径',
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

test('admin content editor reuses historical standard-script scenes as selectable suggestions', async () => {
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url === '/admin/content-categories') {
      return { data: { items: [] } }
    }
    if (url === '/admin/content-scenes') {
      return { data: { items: ['价格异议', '回款催收'] } }
    }
    if (url === '/admin/departments') {
      return { data: { items: [] } }
    }
    return { data: {} }
  })

  const { container, getByLabelText } = await renderAdmin('/admin/contents/new')

  await fireEvent.update(getByLabelText('内容类型'), 'standard_script')

  const sceneSelect = getByLabelText('场景')
  expect(sceneSelect.tagName).toBe('SELECT')
  const sceneOptions = Array.from(sceneSelect.querySelectorAll('option')).map((option) => option.getAttribute('value'))
  expect(sceneOptions).toContain('价格异议')
  expect(sceneOptions).toContain('回款催收')
})

test('admin content editor imports Word or PDF into the new draft form', async () => {
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url === '/admin/content-categories') {
      return { data: { items: ['价格口径', 'Token 电池'] } }
    }
    if (url === '/admin/content-scenes') {
      return { data: { items: ['价格异议', '客户质疑价格偏高'] } }
    }
    if (url === '/admin/departments') {
      return { data: { items: [] } }
    }
    return { data: {} }
  })
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async (url: string) => {
    if (url === '/admin/content-import/parse') {
      return {
        data: {
          content_type: 'standard_script',
          single_draft: {
            title: '客户价格异议标准话术',
            category: '价格口径',
            summary: '价格异议摘要',
            body: '导入后的正文',
            structured_payload: {
              scene: '客户质疑价格偏高',
              recommended_speech: '先解释价值',
              forbidden_speech: '不要直接降价',
              notes: '核对数字',
            },
            warnings: ['未识别到完整禁用说法，请管理员补充。'],
          },
          split_suggestions: [],
          raw_text: '原始解析文本',
          parse_method: 'docx_local',
          warnings: ['第 1 页采用本地解析。'],
          pages: [],
        },
      }
    }
    return {
      data: contentItem({ id: 12, content_type: 'standard_script' }),
    }
  })

  const { container, getByLabelText, getByRole, getByText } = await renderAdmin('/admin/contents/new')

  expect(getByText('从 Word/PDF 导入')).toBeInTheDocument()
  expect(getByRole('button', { name: '解析并填入表单' })).toBeDisabled()

  await fireEvent.update(getByLabelText('内容类型'), 'standard_script')
  await fireEvent.change(getByLabelText('导入文件'), {
    target: {
      files: [
        new File(['docx'], 'standard.docx', {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
      ],
    },
  })
  await fireEvent.click(getByRole('button', { name: '解析并填入表单' }))

  await waitFor(() => expect(getByLabelText('标题')).toHaveValue('客户价格异议标准话术'))
  const categoryInput = getByLabelText('分类') as HTMLInputElement
  expect(categoryInput).toHaveValue('价格口径')
  expect(categoryInput.tagName).toBe('INPUT')
  expect(categoryInput.getAttribute('list')).toBe('content-category-options')
  const categoryOptions = Array.from(container.querySelectorAll('#content-category-options option')).map((option) =>
    option.getAttribute('value'),
  )
  expect(categoryOptions).toContain('价格口径')
  expect(categoryOptions).toContain('Token 电池')
  expect(getByLabelText('摘要')).toHaveValue('价格异议摘要')
  expect(getByLabelText('正文')).toHaveValue('导入后的正文')
  expect(getByLabelText('场景')).toHaveValue('客户质疑价格偏高')
  expect(getByLabelText('场景').tagName).toBe('SELECT')
  const sceneOptions = Array.from(getByLabelText('场景').querySelectorAll('option')).map((option) =>
    option.getAttribute('value'),
  )
  expect(sceneOptions).toContain('价格异议')
  expect(sceneOptions).toContain('客户质疑价格偏高')
  expect(getByLabelText('推荐说法')).toHaveValue('先解释价值')
  expect(getByText('第 1 页采用本地解析。')).toBeInTheDocument()
  expect(getByText('未识别到完整禁用说法，请管理员补充。')).toBeInTheDocument()
  expect(post).toHaveBeenCalledWith('/admin/content-import/parse', expect.any(FormData), {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })

  await fireEvent.update(getByLabelText('权限级别'), 'general')
  await fireEvent.click(getByRole('button', { name: '保存草稿' }))

  await waitFor(() =>
    expect(post).toHaveBeenLastCalledWith('/admin/contents', {
      body: '导入后的正文',
      category: '价格口径',
      content_type: 'standard_script',
      permission_level: 'general',
      structured_payload: {
        forbidden_speech: '不要直接降价',
        notes: '核对数字',
        recommended_speech: '先解释价值',
        scene: '客户质疑价格偏高',
      },
      summary: '价格异议摘要',
      title: '客户价格异议标准话术',
    }),
  )
})

test('admin content editor rejects legacy doc import before calling backend', async () => {
  const post = vi.spyOn(apiClient, 'post')
  const { getByLabelText, getByRole, getByText } = await renderAdmin('/admin/contents/new')

  await fireEvent.update(getByLabelText('内容类型'), 'base_script')
  await fireEvent.change(getByLabelText('导入文件'), {
    target: {
      files: [new File(['doc'], 'legacy.doc', { type: 'application/msword' })],
    },
  })
  await fireEvent.click(getByRole('button', { name: '解析并填入表单' }))

  expect(getByText('仅支持 .docx 和 .pdf。老版 .doc 文件请另存为 .docx 后上传。')).toBeInTheDocument()
  expect(post).not.toHaveBeenCalledWith('/admin/content-import/parse', expect.anything(), expect.anything())
})

test('admin content editor shows backend import error message', async () => {
  const post = vi.spyOn(apiClient, 'post').mockRejectedValue({
    message: 'AI 结构化失败，已使用本地解析文本生成保守草稿，请人工核对字段。',
  })
  const { getByLabelText, getByRole, getByText } = await renderAdmin('/admin/contents/new')

  await fireEvent.update(getByLabelText('内容类型'), 'standard_script')
  await fireEvent.change(getByLabelText('导入文件'), {
    target: {
      files: [
        new File(['docx'], 'standard.docx', {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
      ],
    },
  })
  await fireEvent.click(getByRole('button', { name: '解析并填入表单' }))

  await waitFor(() =>
    expect(
      getByText('AI 结构化失败，已使用本地解析文本生成保守草稿，请人工核对字段。'),
    ).toBeInTheDocument(),
  )
  expect(post).toHaveBeenCalledWith('/admin/content-import/parse', expect.any(FormData), {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
})

test('admin content editor saves selected split import candidates as drafts', async () => {
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url === '/admin/content-categories') {
      return { data: { items: ['价格口径', 'Token 电池'] } }
    }
    if (url === '/admin/content-scenes') {
      return { data: { items: ['高置信场景', '投标答疑'] } }
    }
    if (url === '/admin/departments') {
      return { data: { items: [] } }
    }
    return { data: {} }
  })
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async (url: string) => {
    if (url === '/admin/content-import/parse') {
      return {
        data: {
          content_type: 'standard_script',
          single_draft: {
            title: '客户价格异议标准话术',
            category: '价格口径',
            summary: '价格异议摘要',
            body: '导入后的正文',
            structured_payload: {
              scene: '客户质疑价格偏高',
              recommended_speech: '先解释价值',
              forbidden_speech: '不要直接降价',
              notes: '核对数字',
            },
            warnings: [],
          },
          split_suggestions: [
            {
              temp_id: 'draft-1',
              suggested_content_type: 'standard_script',
              title: '高置信候选',
              category: null,
              summary: '高置信摘要',
              body: '高置信正文',
              structured_payload: {
                scene: '高置信场景',
                recommended_speech: '高置信推荐说法',
                forbidden_speech: '高置信禁用说法',
                notes: '高置信注意事项',
              },
              source_span: { start_block: 1, end_block: 3 },
              confidence: 'high',
              warnings: [],
            },
            {
              temp_id: 'draft-2',
              suggested_content_type: 'standard_script',
              title: '低置信候选',
              category: '价格口径',
              summary: '低置信摘要',
              body: '低置信正文',
              structured_payload: {
                scene: '低置信场景',
                recommended_speech: '低置信推荐说法',
              },
              source_span: { start_block: 4, end_block: 5 },
              confidence: 'low',
              warnings: [],
            },
          ],
          raw_text: '原始解析文本',
          parse_method: 'docx_local',
          warnings: [],
          pages: [],
        },
      }
    }
    return {
      data: contentItem({ id: 12, content_type: 'standard_script' }),
    }
  })

  const { getByLabelText, getByRole, getByTestId, getByText } = await renderAdmin('/admin/contents/new')

  await fireEvent.update(getByLabelText('内容类型'), 'standard_script')
  await fireEvent.change(getByLabelText('导入文件'), {
    target: {
      files: [
        new File(['docx'], 'standard.docx', {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
      ],
    },
  })
  await fireEvent.click(getByRole('button', { name: '解析并填入表单' }))

  await waitFor(() => expect(getByText('已填入：客户价格异议标准话术')).toBeInTheDocument())
  await fireEvent.click(getByRole('button', { name: '拆解候选' }))
  expect(getByText('高置信候选')).toBeInTheDocument()
  expect(getByText('低置信候选')).toBeInTheDocument()
  const candidateFields = getByTestId('split-candidate-fields-draft-1')
  expect(within(candidateFields).getByLabelText('候选分类').tagName).toBe('SELECT')
  expect(within(candidateFields).getByLabelText('候选场景').tagName).toBe('SELECT')
  await fireEvent.change(within(candidateFields).getByLabelText('候选分类'), {
    target: { value: 'Token 电池' },
  })
  await fireEvent.change(within(candidateFields).getByLabelText('候选场景'), {
    target: { value: '投标答疑' },
  })

  await fireEvent.update(getByLabelText('权限级别'), 'general')
  await fireEvent.click(getByRole('button', { name: '保存选中为草稿' }))

  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents', {
      body: '高置信正文',
      category: 'Token 电池',
      content_type: 'standard_script',
      permission_level: 'general',
      structured_payload: {
        forbidden_speech: '高置信禁用说法',
        notes: '高置信注意事项',
        recommended_speech: '高置信推荐说法',
        scene: '投标答疑',
      },
      summary: '高置信摘要',
      title: '高置信候选',
    }),
  )
  expect(post).not.toHaveBeenCalledWith(
    '/admin/contents',
    expect.objectContaining({ title: '低置信候选' }),
  )
})

test('admin content editor shows split candidate detail and missing required fields before saving', async () => {
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url === '/admin/content-categories') {
      return { data: { items: ['Token 电池', '价格口径'] } }
    }
    if (url === '/admin/content-scenes') {
      return { data: { items: ['价格异议', '投标答疑'] } }
    }
    if (url === '/admin/departments') {
      return { data: { items: [] } }
    }
    return { data: {} }
  })
  vi.spyOn(apiClient, 'post').mockImplementation(async (url: string) => {
    if (url === '/admin/content-import/parse') {
      return {
        data: {
          content_type: 'standard_script',
          single_draft: {
            title: 'Token 电池文档',
            category: 'Token 电池',
            summary: '摘要',
            body: '正文',
            structured_payload: {},
            warnings: [],
          },
          split_suggestions: [
            {
              temp_id: 'draft-1',
              suggested_content_type: 'standard_script',
              title: '缺字段候选',
              category: 'Token 电池',
              summary: '摘要',
              body: '完整候选正文',
              structured_payload: {
                scene: '',
                recommended_speech: '',
                forbidden_speech: '',
                notes: '',
              },
              source_span: { start_block: 1, end_block: 2 },
              confidence: 'high',
              warnings: [],
              validation_status: 'invalid',
              is_saveable: false,
              missing_fields: ['场景', '推荐说法'],
              quality_warnings: ['缺少标准话术必填字段'],
            },
          ],
          raw_text: '原始解析文本',
          parse_method: 'docx_local_image_ocr',
          warnings: [],
          pages: [],
        },
      }
    }
    return { data: contentItem({ id: 12, content_type: 'standard_script' }) }
  })

  const { container, getByLabelText, getByRole, getByText, findByRole } = await renderAdmin(
    '/admin/contents/new',
  )
  await fireEvent.update(getByLabelText('内容类型'), 'standard_script')
  await fireEvent.change(getByLabelText('导入文件'), {
    target: {
      files: [
        new File(['docx'], 'token.docx', {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
      ],
    },
  })
  await fireEvent.click(getByRole('button', { name: '解析并填入表单' }))
  await fireEvent.click(await findByRole('button', { name: '拆解候选' }))
  const candidateTitle = getByText('缺字段候选')
  const candidateToggle = candidateTitle.closest('label')
  expect(candidateToggle).toHaveClass('import-result__candidate-toggle')
  expect(within(candidateToggle as HTMLElement).getByRole('checkbox')).toHaveClass(
    'import-result__candidate-checkbox',
  )
  const candidateFields = container.querySelector('[data-testid="split-candidate-fields-draft-1"]')
  expect(candidateFields).toBeInTheDocument()
  const cardCategorySelect = within(candidateFields as HTMLElement).getByLabelText('候选分类')
  expect(cardCategorySelect.tagName).toBe('SELECT')
  const cardCategoryOptions = Array.from(cardCategorySelect.querySelectorAll('option')).map((option) =>
    option.getAttribute('value'),
  )
  expect(cardCategoryOptions).toContain('Token 电池')
  expect(cardCategoryOptions).toContain('价格口径')
  const cardSceneSelect = within(candidateFields as HTMLElement).getByLabelText('候选场景')
  expect(cardSceneSelect.tagName).toBe('SELECT')
  const cardSceneOptions = Array.from(cardSceneSelect.querySelectorAll('option')).map((option) =>
    option.getAttribute('value'),
  )
  expect(cardSceneOptions).toContain('价格异议')
  expect(cardSceneOptions).toContain('投标答疑')
  await fireEvent.click(getByRole('button', { name: '查看并编辑' }))

  const dialog = getByRole('dialog', { name: '拆解候选详情' })
  expect(dialog).toBeInTheDocument()
  expect(within(dialog).getByText('完整候选正文')).toBeInTheDocument()
  expect(within(dialog).getByText(/缺少字段/)).toBeInTheDocument()
  const splitCategorySelect = within(dialog).getByLabelText('候选分类')
  expect(splitCategorySelect.tagName).toBe('SELECT')
  const splitCategoryOptions = Array.from(splitCategorySelect.querySelectorAll('option')).map((option) =>
    option.getAttribute('value'),
  )
  expect(splitCategoryOptions).toContain('Token 电池')
  expect(splitCategoryOptions).toContain('价格口径')
  const splitSceneSelect = within(dialog).getByLabelText('候选场景')
  expect(splitSceneSelect.tagName).toBe('SELECT')
  const splitSceneOptions = Array.from(splitSceneSelect.querySelectorAll('option')).map((option) =>
    option.getAttribute('value'),
  )
  expect(splitSceneOptions).toContain('价格异议')
  expect(splitSceneOptions).toContain('投标答疑')
  expect(within(dialog).getByLabelText('候选推荐说法')).toBeInTheDocument()
})

test('admin content editor saves valid split candidates and reports invalid selected candidates', async () => {
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url === '/admin/content-categories') {
      return { data: { items: ['价格口径'] } }
    }
    if (url === '/admin/departments') {
      return { data: { items: [] } }
    }
    return { data: {} }
  })
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async (url: string) => {
    if (url === '/admin/content-import/parse') {
      return {
        data: {
          content_type: 'standard_script',
          single_draft: {
            title: '客户价格异议标准话术',
            category: '价格口径',
            summary: '价格异议摘要',
            body: '导入后的正文',
            structured_payload: {},
            warnings: [],
          },
          split_suggestions: [
            {
              temp_id: 'valid-1',
              suggested_content_type: 'standard_script',
              title: '有效候选',
              category: '价格口径',
              summary: '有效摘要',
              body: '有效正文',
              structured_payload: {
                scene: '有效场景',
                recommended_speech: '有效推荐说法',
                forbidden_speech: '',
                notes: '',
              },
              source_span: { start_block: 1, end_block: 2 },
              confidence: 'high',
              warnings: [],
              validation_status: 'valid',
              is_saveable: true,
              missing_fields: [],
              quality_warnings: [],
            },
            {
              temp_id: 'invalid-1',
              suggested_content_type: 'standard_script',
              title: '缺字段候选',
              category: '价格口径',
              summary: '缺字段摘要',
              body: '缺字段正文',
              structured_payload: {
                scene: '',
                recommended_speech: '',
              },
              source_span: { start_block: 3, end_block: 4 },
              confidence: 'high',
              warnings: [],
              validation_status: 'invalid',
              is_saveable: false,
              missing_fields: ['场景', '推荐说法'],
              quality_warnings: [],
            },
          ],
          raw_text: '原始解析文本',
          parse_method: 'docx_local',
          warnings: [],
          pages: [],
        },
      }
    }
    return {
      data: contentItem({ id: 12, content_type: 'standard_script' }),
    }
  })

  const { getByLabelText, getByRole, getByText } = await renderAdmin('/admin/contents/new')

  await fireEvent.update(getByLabelText('内容类型'), 'standard_script')
  await fireEvent.change(getByLabelText('导入文件'), {
    target: {
      files: [
        new File(['docx'], 'standard.docx', {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
      ],
    },
  })
  await fireEvent.click(getByRole('button', { name: '解析并填入表单' }))
  await waitFor(() => expect(getByText('已填入：客户价格异议标准话术')).toBeInTheDocument())
  await fireEvent.click(getByRole('button', { name: '拆解候选' }))
  await fireEvent.update(getByLabelText('权限级别'), 'general')
  await fireEvent.click(getByRole('button', { name: '保存选中为草稿' }))

  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/contents', {
      body: '有效正文',
      category: '价格口径',
      content_type: 'standard_script',
      permission_level: 'general',
      structured_payload: {
        forbidden_speech: '',
        notes: '',
        recommended_speech: '有效推荐说法',
        scene: '有效场景',
      },
      summary: '有效摘要',
      title: '有效候选',
    }),
  )
  expect(post).not.toHaveBeenCalledWith(
    '/admin/contents',
    expect.objectContaining({ title: '缺字段候选' }),
  )
  expect(getByText('以下拆解候选缺少必填字段，未保存：缺字段候选（场景、推荐说法）')).toBeInTheDocument()
})

test('admin content editor keeps import progress gradual before the parse response', async () => {
  vi.useFakeTimers()
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url === '/admin/content-categories') {
      return { data: { items: [] } }
    }
    if (url === '/admin/departments') {
      return { data: { items: [] } }
    }
    return { data: {} }
  })
  const pending = deferred<{ data: Record<string, unknown> }>()
  vi.spyOn(apiClient, 'post').mockReturnValue(pending.promise)

  const { getByLabelText, getByRole, getByText } = await renderAdmin('/admin/contents/new')
  await fireEvent.update(getByLabelText('内容类型'), 'base_script')
  await fireEvent.change(getByLabelText('导入文件'), {
    target: {
      files: [
        new File(['docx'], 'token.docx', {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
      ],
    },
  })
  await fireEvent.click(getByRole('button', { name: '解析并填入表单' }))
  await vi.advanceTimersByTimeAsync(500)
  const earlyProgress = Number(getByText(/%$/).textContent?.replace('%', ''))
  expect(earlyProgress).toBeGreaterThan(0)
  expect(earlyProgress).toBeLessThan(40)
  pending.resolve({
    data: {
      content_type: 'base_script',
      single_draft: {
        title: '导入标题',
        category: '分类',
        summary: '摘要',
        body: '正文',
        structured_payload: { points: ['要点'] },
        warnings: [],
      },
      split_suggestions: [],
      raw_text: '原始解析文本',
      parse_method: 'docx_local',
      warnings: [],
      pages: [],
    },
  })
  await vi.advanceTimersByTimeAsync(1000)
  await waitFor(() => expect(getByText('100%')).toBeInTheDocument())
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
