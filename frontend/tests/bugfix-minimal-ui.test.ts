import { fireEvent, render, waitFor } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import App from '../src/App.vue'
import { apiClient } from '../src/api/client'
import { listMustReads } from '../src/api/content'
import { getQuiz, submitQuiz } from '../src/api/quiz'
import { createAppRouter } from '../src/router'
import { useAuthStore, type AuthUser } from '../src/stores/auth'

vi.mock('../src/api/content', () => ({
  listMustReads: vi.fn(),
}))

vi.mock('../src/api/quiz', () => ({
  getQuiz: vi.fn(),
  submitQuiz: vi.fn(),
}))

const mockedListMustReads = vi.mocked(listMustReads)
const mockedGetQuiz = vi.mocked(getQuiz)
const mockedSubmitQuiz = vi.mocked(submitQuiz)

const adminUser: AuthUser = {
  id: 1,
  username: 'admin',
  display_name: '管理员',
  account_type: 'admin',
  content_level: 'full',
}

const employeeUser: AuthUser = {
  id: 2,
  username: 'employee',
  display_name: '员工',
  account_type: 'general_user',
  content_level: 'general',
}

function getButton(container: Element, text: string): HTMLElement {
  const button = Array.from(container.querySelectorAll('button')).find((candidate) =>
    candidate.textContent?.includes(text),
  )
  if (!button) {
    throw new Error(`Button not found: ${text}`)
  }
  return button
}

function mustReadTitles(container: Element) {
  return Array.from(container.querySelectorAll('.content-list__item strong')).map((item) =>
    item.textContent?.trim(),
  )
}

async function renderRoute(path: string, user: AuthUser) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createAppRouter(createMemoryHistory())
  useAuthStore().setSession('token', user)
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
  mockedListMustReads.mockReset()
  mockedGetQuiz.mockReset()
  mockedSubmitQuiz.mockReset()
})

test('admin reset password shows a panel-level validation message for short passwords', async () => {
  vi.spyOn(apiClient, 'get').mockImplementation((url: string) => {
    if (url === '/admin/departments') {
      return Promise.resolve({ data: { items: [], total: 0, page: 1, page_size: 20 } })
    }
    return Promise.resolve({
      data: {
        items: [
          {
            id: 7,
            username: 'phase9-user',
            display_name: '员工',
            account_type: 'general_user',
            content_level: 'general',
            department_id: null,
            department_name: null,
            is_active: true,
            updated_at: '2026-06-18T08:30:00Z',
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
  })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { reset: true } })

  const { container } = await renderRoute('/admin/users', adminUser)

  await waitFor(() => expect(container.textContent).toContain('phase9-user'))
  await fireEvent.click(getButton(container, '重置密码'))
  const passwordInput = container.querySelector<HTMLInputElement>(
    '.admin-reset-panel input[type="password"]',
  )
  expect(passwordInput).toHaveAttribute('minlength', '8')

  await fireEvent.update(passwordInput as HTMLInputElement, '1234567')
  await fireEvent.click(getButton(container, '确认重置'))

  expect(container.textContent).toContain('新密码至少 8 位')
  expect(post).not.toHaveBeenCalledWith('/admin/users/7/reset-password', expect.anything())
})

test('admin content editor exposes fixed and historical category suggestions while allowing typing', async () => {
  const get = vi.spyOn(apiClient, 'get').mockImplementation((url: string) => {
    if (url === '/admin/content-categories') {
      return Promise.resolve({ data: { items: ['回款催收'] } })
    }
    return Promise.resolve({ data: { items: [], total: 0, page: 1, page_size: 20 } })
  })

  const { container } = await renderRoute('/admin/contents/new', adminUser)

  await waitFor(() => expect(get).toHaveBeenCalledWith('/admin/content-categories'))
  const categoryInput = container.querySelector<HTMLInputElement>(
    'input[list="content-category-options"]',
  )
  const options = Array.from(container.querySelectorAll('#content-category-options option')).map(
    (option) => option.getAttribute('value'),
  )

  expect(categoryInput).toBeInTheDocument()
  expect(options).toContain('价格口径')
  expect(options).toContain('回款催收')

  await fireEvent.update(categoryInput as HTMLInputElement, '并网流程')
  expect((categoryInput as HTMLInputElement).value).toBe('并网流程')
})

test('must-read list supports category and scope filters plus ten-item paging', async () => {
  mockedListMustReads.mockResolvedValue({
    items: Array.from({ length: 11 }, (_, index) => ({
      id: index + 1,
      title: `必读 ${index + 1}`,
      category: index === 10 ? '风控口径' : '价格口径',
      published_at: '2026-06-17T09:00:00Z',
      effective_at: '2026-06-18T00:00:00Z',
      permission_level: 'general',
      scope_type: index === 10 ? 'department' : 'global',
      department_id: index === 10 ? 1 : null,
      department_name: index === 10 ? 'A部门' : null,
      update_level: 'medium',
      update_body: '更新正文',
      adjustment_points: ['要点'],
    })),
  })

  const { container } = await renderRoute('/app/must-reads', employeeUser)

  await waitFor(() => expect(container.textContent).toContain('必读 10'))
  expect(mustReadTitles(container)).not.toContain('必读 11')

  await fireEvent.click(getButton(container, '下一页'))
  expect(mustReadTitles(container)).toEqual(['必读 11'])

  const selects = container.querySelectorAll<HTMLSelectElement>('select')
  await fireEvent.update(selects[0], '风控口径')

  expect(mustReadTitles(container)).toEqual(['必读 11'])

  await fireEvent.update(selects[1], 'department')
  expect(mustReadTitles(container)).toEqual(['必读 11'])
})

test('quiz page loads latest mode by default, blocks incomplete submit, and locks answers after submit', async () => {
  mockedGetQuiz.mockResolvedValue({
    items: [
      {
        id: 1,
        question: 'Question 1',
        options: ['A', 'B'],
        explanation: null,
        related_content_id: null,
        related_content_type: null,
        related_content_category: '价格口径',
        permission_level: 'general',
        status: 'enabled',
      },
      {
        id: 2,
        question: 'Question 2',
        options: ['A', 'B'],
        explanation: null,
        related_content_id: null,
        related_content_type: null,
        related_content_category: '价格口径',
        permission_level: 'general',
        status: 'enabled',
      },
    ],
  })
  mockedSubmitQuiz.mockResolvedValue({
    results: [
      {
        question_id: 1,
        selected_answer: 'A',
        is_correct: true,
        correct_answer: 'A',
        explanation: '解析 1',
        related_content_id: null,
        related_content_type: null,
      },
      {
        question_id: 2,
        selected_answer: 'B',
        is_correct: false,
        correct_answer: 'A',
        explanation: '解析 2',
        related_content_id: null,
        related_content_type: null,
      },
    ],
  })

  const { container, getByLabelText } = await renderRoute('/app/quiz', employeeUser)

  await waitFor(() => expect(container.textContent).toContain('Question 2'))
  expect(mockedGetQuiz).toHaveBeenCalledWith({ mode: 'latest' })

  await fireEvent.click(getByLabelText('Question 1 A'))
  await fireEvent.click(getButton(container, '提交答案'))

  expect(container.textContent).toContain('请先完成所有题目')
  expect(mockedSubmitQuiz).not.toHaveBeenCalled()

  await fireEvent.click(getByLabelText('Question 2 B'))
  await fireEvent.click(getButton(container, '提交答案'))

  await waitFor(() => expect(container.textContent).toContain('解析 2'))
  expect(getByLabelText('Question 1 A')).toBeDisabled()
  expect(getByLabelText('Question 2 B')).toBeDisabled()
})
