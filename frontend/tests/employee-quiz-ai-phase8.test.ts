import { fireEvent, render, waitFor } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import AiAnswerPage from '../src/pages/app/AiAnswerPage.vue'
import EmployeeHomePage from '../src/pages/EmployeeHomePage.vue'
import QuizPage from '../src/pages/app/QuizPage.vue'
import { askRagStream } from '../src/api/rag'
import { getQuiz, submitQuiz } from '../src/api/quiz'
import { createAppRouter } from '../src/router'
import { useAuthStore, type AuthUser } from '../src/stores/auth'

vi.mock('../src/api/rag', () => ({
  askRagStream: vi.fn(),
}))

vi.mock('../src/api/quiz', () => ({
  getQuiz: vi.fn(),
  submitQuiz: vi.fn(),
}))

const mockedAskRagStream = vi.mocked(askRagStream)
const mockedGetQuiz = vi.mocked(getQuiz)
const mockedSubmitQuiz = vi.mocked(submitQuiz)

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const employeeUser: AuthUser = {
  id: 2,
  username: 'general',
  display_name: '通用员工',
  account_type: 'general_user',
  content_level: 'general',
}

async function renderAppPage(component: object, path = '/app') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createAppRouter(createMemoryHistory())
  const auth = useAuthStore()
  auth.setSession('token', employeeUser)
  await router.push(path)
  await router.isReady()

  return {
    ...render(component, {
      global: {
        plugins: [pinia, router],
      },
    }),
    router,
  }
}

beforeEach(() => {
  sessionStorage.clear()
  mockedAskRagStream.mockReset()
  mockedGetQuiz.mockReset()
  mockedSubmitQuiz.mockReset()
})

test('employee home rejects empty AI questions and routes non-empty questions to the RAG request path', async () => {
  const { getByLabelText, getByRole, getByText, router } = await renderAppPage(EmployeeHomePage, '/app')

  await fireEvent.click(getByRole('button', { name: '提问' }))
  expect(getByText('请输入要查询的问题')).toBeInTheDocument()

  await fireEvent.update(getByLabelText('AI 问题'), ' 如何介绍新产品 ')
  await fireEvent.click(getByRole('button', { name: '提问' }))

  await waitFor(() => {
    expect(router.currentRoute.value.name).toBe('employee-ai-answer')
  })
  expect(router.currentRoute.value.query.question).toBe('如何介绍新产品')
})

test('quiz page renders five to ten questions and records each selected answer separately', async () => {
  mockedGetQuiz.mockResolvedValue({
    items: Array.from({ length: 5 }, (_, index) => ({
      id: index + 1,
      question: `题目 ${index + 1}`,
      options: ['A', 'B', 'C'],
      explanation: null,
      related_content_id: null,
      related_content_type: null,
      permission_level: 'general',
      status: 'enabled',
    })),
  })

  const { getByLabelText, getByText } = await renderAppPage(QuizPage, '/app/quiz')

  await waitFor(() => {
    expect(getByText('题目 5')).toBeInTheDocument()
  })

  await fireEvent.click(getByLabelText('题目 1 A'))
  await fireEvent.click(getByLabelText('题目 2 B'))

  expect(mockedSubmitQuiz).not.toHaveBeenCalled()
  expect((getByLabelText('题目 1 A') as HTMLInputElement).checked).toBe(true)
  expect((getByLabelText('题目 2 B') as HTMLInputElement).checked).toBe(true)
})

test('quiz submit sends selected answers, disables duplicate submit, and renders result explanations', async () => {
  mockedGetQuiz.mockResolvedValue({
    items: [
      {
        id: 1,
        question: '题目 1',
        options: ['A', 'B'],
        explanation: null,
        related_content_id: 21,
        related_content_type: 'must_read',
        permission_level: 'general',
        status: 'enabled',
      },
    ],
  })
  let resolveSubmit: (value: Awaited<ReturnType<typeof submitQuiz>>) => void = () => {}
  mockedSubmitQuiz.mockReturnValue(
    new Promise((resolve) => {
      resolveSubmit = resolve
    }),
  )

  const { getByLabelText, getByRole, getByText } = await renderAppPage(QuizPage, '/app/quiz')

  await waitFor(() => {
    expect(getByText('题目 1')).toBeInTheDocument()
  })
  await fireEvent.click(getByLabelText('题目 1 A'))
  await fireEvent.click(getByRole('button', { name: '提交答案' }))

  expect(mockedSubmitQuiz).toHaveBeenCalledWith({
    answers: [{ question_id: 1, selected_answer: 'A' }],
  })
  expect(getByRole('button', { name: '提交中' })).toBeDisabled()

  resolveSubmit({
    results: [
      {
        question_id: 1,
        selected_answer: 'A',
        is_correct: false,
        correct_answer: 'B',
        explanation: '应先说明适用范围。',
        related_content_id: 21,
        related_content_type: 'must_read',
      },
    ],
  })

  await waitFor(() => {
    expect(getByText('回答错误')).toBeInTheDocument()
  })
  expect(getByText('正确答案：B')).toBeInTheDocument()
  expect(getByText('应先说明适用范围。')).toBeInTheDocument()
  expect(getByRole('link', { name: '查看关联话术' })).toHaveAttribute(
    'href',
    '/app/must-reads/21',
  )
})

test('quiz result links route script types and hide relations without a content type', async () => {
  mockedGetQuiz.mockResolvedValue({
    items: [
      {
        id: 1,
        question: '基础话术题',
        options: ['A', 'B'],
        explanation: null,
        related_content_id: 31,
        related_content_type: 'base_script',
        permission_level: 'general',
        status: 'enabled',
      },
      {
        id: 2,
        question: '标准话术题',
        options: ['A', 'B'],
        explanation: null,
        related_content_id: 32,
        related_content_type: 'standard_script',
        permission_level: 'general',
        status: 'enabled',
      },
      {
        id: 3,
        question: '无类型关联题',
        options: ['A', 'B'],
        explanation: null,
        related_content_id: 33,
        related_content_type: null,
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
        explanation: null,
        related_content_id: 31,
        related_content_type: 'base_script',
      },
      {
        question_id: 2,
        selected_answer: 'A',
        is_correct: true,
        correct_answer: 'A',
        explanation: null,
        related_content_id: 32,
        related_content_type: 'standard_script',
      },
      {
        question_id: 3,
        selected_answer: 'A',
        is_correct: true,
        correct_answer: 'A',
        explanation: null,
        related_content_id: 33,
        related_content_type: null,
      },
    ],
  })

  const { getAllByRole, getByLabelText, getByRole, getByText } = await renderAppPage(
    QuizPage,
    '/app/quiz',
  )

  await waitFor(() => {
    expect(getByText('无类型关联题')).toBeInTheDocument()
  })
  await fireEvent.click(getByLabelText('基础话术题 A'))
  await fireEvent.click(getByLabelText('标准话术题 A'))
  await fireEvent.click(getByLabelText('无类型关联题 A'))
  await fireEvent.click(getByRole('button', { name: '提交答案' }))

  await waitFor(() => {
    expect(getAllByRole('link', { name: '查看关联话术' })).toHaveLength(2)
  })
  expect(
    getAllByRole('link', { name: '查看关联话术' }).map((link) => link.getAttribute('href')),
  ).toEqual(['/app/scripts/31', '/app/scripts/32'])
})

test('quiz page does not render score history, ranking, or statistics entries', async () => {
  mockedGetQuiz.mockResolvedValue({ items: [] })

  const { queryByText } = await renderAppPage(QuizPage, '/app/quiz')

  await waitFor(() => {
    expect(mockedGetQuiz).toHaveBeenCalled()
  })
  expect(queryByText('排行')).not.toBeInTheDocument()
  expect(queryByText('分数历史')).not.toBeInTheDocument()
  expect(queryByText('个人统计')).not.toBeInTheDocument()
  expect(queryByText('管理统计')).not.toBeInTheDocument()
})

test('AI answer page shows loading then delegates to stream callback on success', async () => {
  mockedAskRagStream.mockImplementation(async (q, callbacks) => {
    callbacks.onSources?.([{ chunk_id: 1, title: 'Source 1', content_type: 'must_read', update_level: 'minor', updated_at: '2024-01-01', relevance_score: 0.9, content_id: 1, version_id: 1 }])
    callbacks.onContent?.('Chunk 1 ')
    callbacks.onContent?.('Chunk 2')
    callbacks.onDone?.()
  })

  const { getByText, findByText } = await renderAppPage(AiAnswerPage, '/app/ask?question=Hello')

  await waitFor(() => {
    expect(getByText('Chunk 1 Chunk 2')).toBeInTheDocument()
  })

  expect(mockedAskRagStream).toHaveBeenCalledWith('Hello', expect.any(Object), expect.any(AbortSignal))
  expect(getByText('Source 1')).toBeInTheDocument()
})

test('AI answer page shows error state on network error', async () => {
  mockedAskRagStream.mockImplementation(async (q, callbacks) => {
    callbacks.onError?.('Mocked network error')
  })

  const { getByText } = await renderAppPage(AiAnswerPage, '/app/ask?question=Fail')

  await waitFor(() => {
    expect(getByText('Mocked network error')).toBeInTheDocument()
  })
})
