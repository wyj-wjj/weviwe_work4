import { fireEvent, render, waitFor } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import App from '../src/App.vue'
import { apiClient } from '../src/api/client'
import { createAppRouter } from '../src/router'
import { useAuthStore } from '../src/stores/auth'

async function renderAdmin(path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createAppRouter(createMemoryHistory())
  useAuthStore().setSession('admin-token', {
    id: 1,
    username: 'admin',
    display_name: '管理员',
    account_type: 'admin',
    content_level: 'full',
  })
  await router.push(path)
  await router.isReady()
  return render(App, {
    global: {
      plugins: [pinia, router],
    },
  })
}

beforeEach(() => {
  sessionStorage.clear()
  vi.restoreAllMocks()
})

test('admin quiz page lists, creates, edits, enables, and disables questions', async () => {
  const quizListResponse = {
    data: {
      items: [
        {
          id: 5,
          question: '应该先做什么？',
          options: ['确认需求', '直接报价'],
          answer: '确认需求',
          explanation: '先确认需求。',
          related_content_id: 2,
          related_version_id: 3,
          related_content_title: '基础接待话术',
          permission_level: 'general',
          status: 'enabled',
          source_type: 'manual',
          review_status: 'approved',
          generation_batch_id: null,
          needs_review: false,
          review_reason: null,
          expires_at: null,
          priority: 0,
          source_valid: true,
          source_invalid_reason: null,
          updated_at: '2026-06-18T08:00:00',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    },
  }
  const get = vi.spyOn(apiClient, 'get').mockImplementation((url: string) => {
    if (url === '/admin/quiz-sets') {
      return Promise.resolve({
        data: {
          items: [
            {
              id: 8,
              title: '消防验收新要求专题测验',
              description: '大更新专题包',
              related_content_id: 2,
              related_version_id: 3,
              update_level: 'major',
              permission_level: 'general',
              status: 'active',
              expires_at: null,
              created_at: '2026-06-18T08:10:00',
              question_count: 2,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        },
      })
    }
    return Promise.resolve(quizListResponse)
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} })
  const patch = vi.spyOn(apiClient, 'patch').mockResolvedValue({ data: {} })

  const { getByLabelText, getByRole, getByText } = await renderAdmin(
    '/admin/quiz-questions',
  )

  await waitFor(() => expect(getByText('应该先做什么？')).toBeInTheDocument())
  expect(getByText('基础接待话术')).toBeInTheDocument()
  expect(getByText('消防验收新要求专题测验')).toBeInTheDocument()
  expect(getByText('2026-06-18 16:00')).toBeInTheDocument()

  await fireEvent.click(getByRole('button', { name: '新建测验题' }))
  await fireEvent.update(getByLabelText('题干'), '新建题目？')
  await fireEvent.update(getByLabelText('选项（每行一个）'), '选项 A\n选项 B')
  await fireEvent.update(getByLabelText('正确答案'), '选项 A')
  await fireEvent.update(getByLabelText('解析'), '新建题解析。')
  await fireEvent.click(getByRole('button', { name: '保存测验题' }))
  await waitFor(() => {
    expect(post).toHaveBeenCalledWith('/admin/quiz-questions', {
      answer: '选项 A',
      explanation: '新建题解析。',
      options: ['选项 A', '选项 B'],
      permission_level: 'general',
      question: '新建题目？',
      related_content_id: null,
      related_version_id: null,
      source_type: 'manual',
      review_status: 'approved',
      generation_batch_id: null,
      needs_review: false,
      review_reason: null,
      expires_at: null,
      priority: 0,
      status: 'enabled',
    })
  })

  await fireEvent.click(getByRole('button', { name: '编辑' }))
  await fireEvent.update(getByLabelText('题干'), '更新后的题干？')
  await fireEvent.update(getByLabelText('选项（每行一个）'), '确认身份\n确认需求')
  await fireEvent.update(getByLabelText('正确答案'), '确认需求')
  await fireEvent.update(getByLabelText('解析'), '先确认身份和需求。')
  await fireEvent.update(getByLabelText('关联话术 ID'), '2')
  await fireEvent.update(getByLabelText('生成批次 ID'), '9')
  await fireEvent.update(getByLabelText('抽题优先级'), '100')
  await fireEvent.update(getByLabelText('过期时间'), '2026-06-30T23:59:59')
  await fireEvent.update(getByLabelText('权限级别'), 'full')
  await fireEvent.update(getByLabelText('状态'), 'disabled')
  await fireEvent.click(getByRole('button', { name: '保存测验题' }))

  await waitFor(() => {
    expect(patch).toHaveBeenCalledWith('/admin/quiz-questions/5', {
      answer: '确认需求',
      explanation: '先确认身份和需求。',
      options: ['确认身份', '确认需求'],
      permission_level: 'full',
      question: '更新后的题干？',
      related_content_id: 2,
      related_version_id: 3,
      source_type: 'manual',
      review_status: 'approved',
      generation_batch_id: 9,
      needs_review: false,
      review_reason: null,
      expires_at: '2026-06-30T23:59:59',
      priority: 100,
      status: 'disabled',
    })
  })

  await fireEvent.click(getByRole('button', { name: '禁用' }))
  expect(post).toHaveBeenCalledWith('/admin/quiz-questions/5/disable')
  await waitFor(() => expect(getByRole('button', { name: '启用' })).toBeInTheDocument())
  await fireEvent.click(getByRole('button', { name: '启用' }))
  expect(post).toHaveBeenCalledWith('/admin/quiz-questions/5/enable')
  expect(get.mock.calls.length).toBeGreaterThan(1)
})

test('admin quiz page reviews pending AI questions with explicit approve and reject actions', async () => {
  const get = vi.spyOn(apiClient, 'get').mockImplementation((url: string) => {
    if (url === '/admin/quiz-sets') {
      return Promise.resolve({
        data: {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
        },
      })
    }
    return Promise.resolve({
      data: {
        items: [
          {
            id: 12,
            question: 'AI 候选题应该如何处理？',
            options: ['审核后启用', '直接上线'],
            answer: '审核后启用',
            explanation: 'AI 题必须审核。',
            related_content_id: 9,
            related_version_id: 15,
            related_content_title: '管理员手测',
            permission_level: 'general',
            status: 'disabled',
            source_type: 'ai_generated',
            review_status: 'pending_review',
            generation_batch_id: 3,
            needs_review: false,
            review_reason: null,
            expires_at: null,
            priority: 100,
            source_valid: true,
            source_invalid_reason: null,
            updated_at: '2026-06-23T08:31:00',
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} })

  const { getByRole, getByText, queryByRole } = await renderAdmin('/admin/quiz-questions')

  await waitFor(() => expect(getByText('AI 候选题应该如何处理？')).toBeInTheDocument())
  expect(getByText('AI 生成 / 待审核')).toBeInTheDocument()
  expect(queryByRole('button', { name: '启用' })).not.toBeInTheDocument()

  await fireEvent.click(getByRole('button', { name: '审核通过并启用' }))
  expect(post).toHaveBeenCalledWith('/admin/quiz-questions/12/approve')

  await waitFor(() => expect(getByRole('button', { name: '驳回' })).toBeEnabled())
  await fireEvent.click(getByRole('button', { name: '驳回' }))
  expect(post).toHaveBeenCalledWith('/admin/quiz-questions/12/reject')
  expect(get.mock.calls.length).toBeGreaterThan(1)
})

test('admin quiz page shows invalid source state and only allows safe rejection', async () => {
  vi.spyOn(apiClient, 'get').mockImplementation((url: string) => {
    if (url === '/admin/quiz-sets') {
      return Promise.resolve({
        data: {
          items: [
            {
              id: 3,
              title: '管理员手测 专题测验',
              description: '旧版本专题包',
              related_content_id: 9,
              related_version_id: 15,
              update_level: 'major',
              permission_level: 'general',
              status: 'inactive',
              expires_at: null,
              created_at: '2026-06-23T08:29:00',
              question_count: 1,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        },
      })
    }
    return Promise.resolve({
      data: {
        items: [
          {
            id: 13,
            question: '旧版本 AI 候选题还能上线吗？',
            options: ['不能', '可以'],
            answer: '不能',
            explanation: '旧版本题目不能上线。',
            related_content_id: 9,
            related_version_id: 15,
            related_content_title: '管理员手测',
            permission_level: 'general',
            status: 'disabled',
            source_type: 'ai_generated',
            review_status: 'pending_review',
            generation_batch_id: 4,
            needs_review: false,
            review_reason: null,
            expires_at: null,
            priority: 100,
            source_valid: false,
            source_invalid_reason: 'source_version_stale',
            updated_at: '2026-06-23T08:31:00',
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} })

  const { getByRole, getByText, queryByRole } = await renderAdmin('/admin/quiz-questions')

  await waitFor(() => expect(getByText('旧版本 AI 候选题还能上线吗？')).toBeInTheDocument())
  expect(getByText('源版本已失效')).toBeInTheDocument()
  expect(getByText('来源失效，禁止上线')).toBeInTheDocument()
  expect(queryByRole('button', { name: '审核通过并启用' })).not.toBeInTheDocument()
  expect(queryByRole('button', { name: '启用' })).not.toBeInTheDocument()

  await fireEvent.click(getByRole('button', { name: '驳回' }))
  expect(post).toHaveBeenCalledWith('/admin/quiz-questions/13/reject')
})

test('admin users page creates, edits, resets, disables, and enables accounts with one-time reset feedback', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [
        {
          id: 7,
          username: 'phase9-user',
          display_name: '阶段九员工',
          account_type: 'general_user',
          content_level: 'general',
          is_active: true,
          updated_at: '2026-06-18T08:30:00',
        },
        {
          id: 8,
          username: 'phase9-disabled',
          display_name: '阶段九禁用员工',
          account_type: 'general_user',
          content_level: 'general',
          is_active: false,
          updated_at: '2026-06-18T08:35:00',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    },
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { reset: true } })
  const patch = vi.spyOn(apiClient, 'patch').mockResolvedValue({ data: {} })

  const { getAllByRole, getByLabelText, getByRole, getByText } = await renderAdmin('/admin/users')

  await waitFor(() => expect(getByText('phase9-user')).toBeInTheDocument())
  expect(getByText('阶段九员工')).toBeInTheDocument()
  expect(getByText('阶段九禁用员工')).toBeInTheDocument()
  expect(getByText('启用')).toBeInTheDocument()

  await fireEvent.click(getByRole('button', { name: '新增账号' }))
  await fireEvent.update(getByLabelText('用户名'), 'new-user')
  await fireEvent.update(getByLabelText('初始密码'), 'temporary-password')
  await fireEvent.update(getByLabelText('展示名'), '新员工')
  await fireEvent.click(getByRole('button', { name: '保存账号' }))
  await waitFor(() => {
    expect(post).toHaveBeenCalledWith('/admin/users', {
      account_type: 'general_user',
      content_level: 'general',
      display_name: '新员工',
      password: 'temporary-password',
      username: 'new-user',
    })
  })

  await fireEvent.click(getAllByRole('button', { name: '编辑' })[0])
  await fireEvent.update(getByLabelText('展示名'), '完整权限员工')
  await fireEvent.update(getByLabelText('账号类型'), 'full_user')
  await fireEvent.update(getByLabelText('内容权限级别'), 'full')
  await fireEvent.click(getByRole('button', { name: '保存账号' }))
  await waitFor(() =>
    expect(patch).toHaveBeenCalledWith('/admin/users/7', {
      account_type: 'full_user',
      content_level: 'full',
      display_name: '完整权限员工',
      is_active: true,
    }),
  )

  await fireEvent.click(getAllByRole('button', { name: '重置密码' })[0])
  await fireEvent.update(getByLabelText('新密码'), 'new-temporary-password')
  await fireEvent.click(getByRole('button', { name: '确认重置' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/admin/users/7/reset-password', {
      password: 'new-temporary-password',
    }),
  )
  expect(getByText('密码已重置，请安全通知该用户；此提示不会再次展示。')).toBeInTheDocument()

  await fireEvent.click(getByRole('button', { name: '禁用账号' }))
  expect(post).toHaveBeenCalledWith('/admin/users/7/disable')
  expect(window.confirm).toHaveBeenCalled()

  await fireEvent.click(getByRole('button', { name: '启用账号' }))
  expect(post).toHaveBeenCalledWith('/admin/users/8/enable')
  expect(get.mock.calls.length).toBeGreaterThan(1)
})

test('admin missed-question page filters status and marks rows handled without analytics dashboard', async () => {
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: {
      items: [
        {
          id: 4,
          question: '这个问题没有标准答案吗？',
          user_id: 2,
          username: 'general-user',
          account_type: 'general_user',
          content_level: 'general',
          asked_at: '2026-06-18T07:00:00',
          status: 'new',
          handled_at: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    },
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: {
      id: 4,
      status: 'handled',
      handled_at: '2026-06-18T09:00:00',
    },
  })

  const { getByLabelText, getByRole, getByText, queryByText } = await renderAdmin(
    '/admin/missed-questions',
  )

  await waitFor(() =>
    expect(getByText('这个问题没有标准答案吗？')).toBeInTheDocument(),
  )
  expect(getByText('general-user')).toBeInTheDocument()
  expect(getByText('通用权限员工 / 通用级')).toBeInTheDocument()
  expect(queryByText('数据看板')).not.toBeInTheDocument()
  expect(queryByText('排行')).not.toBeInTheDocument()

  await fireEvent.update(getByLabelText('处理状态'), 'handled')
  await fireEvent.click(getByRole('button', { name: '筛选' }))
  await waitFor(() =>
    expect(get).toHaveBeenLastCalledWith('/admin/missed-questions', {
      params: { page: 1, page_size: 20, status: 'handled' },
    }),
  )

  await fireEvent.click(getByRole('button', { name: '标记已处理' }))
  expect(post).toHaveBeenCalledWith('/admin/missed-questions/4/mark-handled')
})
