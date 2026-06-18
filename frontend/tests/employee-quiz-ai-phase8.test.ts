import { fireEvent, render, waitFor } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import AiAnswerPage from '../src/pages/app/AiAnswerPage.vue'
import EmployeeHomePage from '../src/pages/EmployeeHomePage.vue'
import QuizPage from '../src/pages/app/QuizPage.vue'
import { askRag } from '../src/api/rag'
import { getQuiz, submitQuiz } from '../src/api/quiz'
import { createAppRouter } from '../src/router'
import { useAuthStore, type AuthUser } from '../src/stores/auth'

vi.mock('../src/api/rag', () => ({
  askRag: vi.fn(),
}))

vi.mock('../src/api/quiz', () => ({
  getQuiz: vi.fn(),
  submitQuiz: vi.fn(),
}))

const mockedAskRag = vi.mocked(askRag)
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
  mockedAskRag.mockReset()
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
      },
    ],
  })

  await waitFor(() => {
    expect(getByText('回答错误')).toBeInTheDocument()
  })
  expect(getByText('正确答案：B')).toBeInTheDocument()
  expect(getByText('应先说明适用范围。')).toBeInTheDocument()
  expect(getByRole('link', { name: '查看关联话术' })).toHaveAttribute('href', '/app/scripts/21')
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

test('AI answer page renders answer, sources, updated time, copy button, and source links', async () => {
  mockedAskRag.mockResolvedValue({
    hit: true,
    answer: '可以先说明服务范围，再给出标准介绍。',
    sources: [
      {
        content_id: 21,
        version_id: 2,
        chunk_id: 3,
        title: '基础开场白',
        content_type: 'base_script',
        updated_at: '2026-06-17T10:00:00',
        relevance_score: 0.91,
      },
    ],
    usage: { total_tokens: 42 },
  })

  const { getByRole, getByText } = await renderAppPage(
    AiAnswerPage,
    '/app/ask?question=%E5%A6%82%E4%BD%95%E4%BB%8B%E7%BB%8D',
  )

  await waitFor(() => {
    expect(getByText('可以先说明服务范围，再给出标准介绍。')).toBeInTheDocument()
  })
  expect(getByText('基础开场白')).toBeInTheDocument()
  expect(getByText('更新时间：2026-06-17 10:00')).toBeInTheDocument()
  expect(getByRole('button', { name: '复制回答' })).toBeInTheDocument()
  expect(getByRole('link', { name: '查看来源' })).toHaveAttribute('href', '/app/scripts/21')
})

test('AI answer page renders fixed miss copy and AI unavailable state', async () => {
  mockedAskRag.mockResolvedValueOnce({
    hit: false,
    answer: '当前没有有效标准口径，请联系管理员。',
    sources: [],
  })

  const missView = await renderAppPage(AiAnswerPage, '/app/ask?question=miss')
  await waitFor(() => {
    expect(missView.getByText('当前没有有效标准口径，请联系管理员。')).toBeInTheDocument()
  })
  missView.unmount()

  mockedAskRag.mockRejectedValueOnce({
    status: 503,
    code: 'ai_unavailable',
    message: '智能问答暂不可用，请稍后重试。',
    details: null,
  })

  const unavailableView = await renderAppPage(AiAnswerPage, '/app/ask?question=down')
  await waitFor(() => {
    expect(unavailableView.getByText('智能问答暂不可用，请稍后重试')).toBeInTheDocument()
  })
})

test('AI page ignores an older success after a newer question succeeds', async () => {
  const oldRequest = deferred<Awaited<ReturnType<typeof askRag>>>()
  const newRequest = deferred<Awaited<ReturnType<typeof askRag>>>()
  mockedAskRag.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)

  const view = await renderAppPage(AiAnswerPage, '/app/ask?question=旧问题')
  await view.router.push('/app/ask?question=新问题')
  newRequest.resolve({ hit: true, answer: '新回答', sources: [] })
  await waitFor(() => expect(view.getByText('新回答')).toBeInTheDocument())

  oldRequest.resolve({ hit: true, answer: '旧回答', sources: [] })
  await oldRequest.promise
  await Promise.resolve()

  expect(view.queryByText('旧回答')).not.toBeInTheDocument()
  expect(view.getByText('问题：新问题')).toBeInTheDocument()
})

test('AI page ignores an older error after a newer question succeeds', async () => {
  const oldRequest = deferred<Awaited<ReturnType<typeof askRag>>>()
  const newRequest = deferred<Awaited<ReturnType<typeof askRag>>>()
  mockedAskRag.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise)

  const view = await renderAppPage(AiAnswerPage, '/app/ask?question=旧问题')
  await view.router.push('/app/ask?question=新问题')
  newRequest.resolve({ hit: true, answer: '新回答', sources: [] })
  await waitFor(() => expect(view.getByText('新回答')).toBeInTheDocument())

  oldRequest.reject({ status: 503, code: 'ai_unavailable' })
  await oldRequest.promise.catch(() => undefined)
  await Promise.resolve()

  expect(view.queryByText('智能问答暂不可用，请稍后重试')).not.toBeInTheDocument()
  expect(view.getByText('新回答')).toBeInTheDocument()
})

test('AI page aborts the active request when it unmounts', async () => {
  const request = deferred<Awaited<ReturnType<typeof askRag>>>()
  mockedAskRag.mockReturnValue(request.promise)

  const view = await renderAppPage(AiAnswerPage, '/app/ask?question=卸载问题')
  await waitFor(() => expect(mockedAskRag).toHaveBeenCalled())
  const signal = mockedAskRag.mock.calls[0]?.[1]

  expect(signal).toBeInstanceOf(AbortSignal)
  expect(signal?.aborted).toBe(false)

  view.unmount()

  expect(signal?.aborted).toBe(true)
  request.reject({ name: 'AbortError' })
  await Promise.resolve()
})

test('employee AI form does not route again for the same normalized question', async () => {
  mockedAskRag.mockResolvedValue({ hit: true, answer: '当前回答', sources: [] })

  const view = await renderAppPage(AiAnswerPage, '/app/ask?question=同一个问题')
  await waitFor(() => expect(view.getByText('当前回答')).toBeInTheDocument())
  const push = vi.spyOn(view.router, 'push')

  await fireEvent.update(view.getByLabelText('AI 问题'), '  同一个问题  ')
  await fireEvent.click(view.getByRole('button', { name: '提问' }))

  expect(push).not.toHaveBeenCalled()
})
