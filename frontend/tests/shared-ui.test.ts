import { fireEvent, render, waitFor } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import AdminHomePage from '../src/pages/AdminHomePage.vue'
import EmployeeHomePage from '../src/pages/EmployeeHomePage.vue'
import { createAppRouter } from '../src/router'
import { useAuthStore, type AuthUser } from '../src/stores/auth'
import AppState from '../src/components/AppState.vue'
import CopyButton from '../src/components/CopyButton.vue'

const originalClipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
const originalExecCommandDescriptor = Object.getOwnPropertyDescriptor(document, 'execCommand')

function setClipboard(writeText: ReturnType<typeof vi.fn>) {
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  })
}

function removeClipboard() {
  Reflect.deleteProperty(navigator, 'clipboard')
}

function setExecCommand(execCommand: ReturnType<typeof vi.fn>) {
  Object.defineProperty(document, 'execCommand', {
    configurable: true,
    value: execCommand,
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  window.getSelection()?.removeAllRanges()
  document.querySelectorAll('[data-copy-test-fixture]').forEach((element) => element.remove())
  document.querySelectorAll('[data-copy-fallback]').forEach((element) => element.remove())

  if (originalClipboardDescriptor) {
    Object.defineProperty(navigator, 'clipboard', originalClipboardDescriptor)
  } else {
    Reflect.deleteProperty(navigator, 'clipboard')
  }

  if (originalExecCommandDescriptor) {
    Object.defineProperty(document, 'execCommand', originalExecCommandDescriptor)
  } else {
    Reflect.deleteProperty(document, 'execCommand')
  }
})

function renderWithAuth(component: object, user: AuthUser) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createAppRouter(createMemoryHistory())
  const auth = useAuthStore()
  auth.setSession('token', user)

  return render(component, {
    global: {
      plugins: [pinia, router],
    },
  })
}

const employeeUser: AuthUser = {
  id: 2,
  username: 'general',
  display_name: '通用员工',
  account_type: 'general_user',
  content_level: 'general',
}

const adminUser: AuthUser = {
  id: 1,
  username: 'admin',
  display_name: '管理员',
  account_type: 'admin',
  content_level: 'full',
}

test('authenticated employee users see the AI entry and three core navigation entries', () => {
  const { getByText, getByLabelText } = renderWithAuth(EmployeeHomePage, employeeUser)

  expect(getByLabelText('AI 问题')).toBeInTheDocument()
  expect(getByText('最新必读')).toBeInTheDocument()
  expect(getByText('标准话术')).toBeInTheDocument()
  expect(getByText('巩固测试')).toBeInTheDocument()
})

test('admin navigation entries render only for administrator users', () => {
  const adminView = renderWithAuth(AdminHomePage, adminUser)
  expect(adminView.getByText('内容管理')).toBeInTheDocument()
  expect(adminView.getByText('测验题管理')).toBeInTheDocument()
  expect(adminView.getByText('账号管理')).toBeInTheDocument()
  expect(adminView.getByText('未命中问题')).toBeInTheDocument()
  adminView.unmount()

  const employeeView = renderWithAuth(AdminHomePage, employeeUser)
  expect(employeeView.queryByText('内容管理')).not.toBeInTheDocument()
})

test.each([
  ['empty', '暂无可查看的内容'],
  ['loading', '加载中'],
  ['permission', '无权查看该内容'],
  ['service', '服务暂不可用，请稍后重试'],
  ['ai-unavailable', '智能问答暂不可用，请稍后重试'],
] as const)('global %s state renders the expected copy', (state, message) => {
  const { getByText } = render(AppState, {
    props: { state },
  })

  expect(getByText(message)).toBeInTheDocument()
})

test('copy button reports success when Clipboard API resolves', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  setClipboard(writeText)
  const view = render(CopyButton, { props: { text: '推荐说法' } })

  await fireEvent.click(view.getByRole('button', { name: '复制' }))

  await waitFor(() => expect(view.getByText('已复制')).toBeInTheDocument())
  expect(writeText).toHaveBeenCalledWith('推荐说法')
})

test('copy button falls back to execCommand and restores the page state when Clipboard API rejects', async () => {
  setClipboard(vi.fn().mockRejectedValue(new Error('denied')))
  const execCommand = vi.fn().mockImplementation((command: string) => {
    expect(command).toBe('copy')
    const textarea = document.querySelector<HTMLTextAreaElement>('[data-copy-fallback]')
    expect(textarea).not.toBeNull()
    expect(document.body.contains(textarea)).toBe(true)
    expect(textarea?.value).toBe('推荐说法')
    expect(textarea?.readOnly).toBe(true)
    expect(document.activeElement).toBe(textarea)
    expect(textarea?.selectionStart).toBe(0)
    expect(textarea?.selectionEnd).toBe('推荐说法'.length)
    return true
  })
  setExecCommand(execCommand)

  const focusedInput = document.createElement('input')
  focusedInput.dataset.copyTestFixture = 'focus'
  document.body.appendChild(focusedInput)
  focusedInput.focus()

  const selectedText = document.createElement('p')
  selectedText.dataset.copyTestFixture = 'selection'
  selectedText.textContent = '保留选择'
  document.body.appendChild(selectedText)
  const range = document.createRange()
  range.selectNodeContents(selectedText)
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)

  const view = render(CopyButton, { props: { text: '推荐说法' } })
  await fireEvent.click(view.getByRole('button', { name: '复制' }))

  await waitFor(() => expect(view.getByText('已复制')).toBeInTheDocument())
  expect(execCommand).toHaveBeenCalledWith('copy')
  expect(document.querySelector('[data-copy-fallback]')).toBeNull()
  expect(document.activeElement).toBe(focusedInput)
  expect(window.getSelection()?.toString()).toBe('保留选择')
})

test('copy button falls back successfully when navigator.clipboard is absent', async () => {
  removeClipboard()
  expect('clipboard' in navigator).toBe(false)
  const execCommand = vi.fn().mockReturnValue(true)
  setExecCommand(execCommand)
  const view = render(CopyButton, { props: { text: '完整话术' } })

  await fireEvent.click(view.getByRole('button', { name: '复制' }))

  await waitFor(() => expect(view.getByText('已复制')).toBeInTheDocument())
  expect(execCommand).toHaveBeenCalledWith('copy')
  expect(document.querySelector('[data-copy-fallback]')).toBeNull()
})

test('copy button reports failure when Clipboard API and execCommand both fail', async () => {
  setClipboard(vi.fn().mockRejectedValue(new Error('denied')))
  const execCommand = vi.fn().mockReturnValue(false)
  setExecCommand(execCommand)
  const view = render(CopyButton, { props: { text: '推荐说法' } })

  await fireEvent.click(view.getByRole('button', { name: '复制' }))

  await waitFor(() => expect(view.getByText('复制失败，请重试')).toBeInTheDocument())
  expect(execCommand).toHaveBeenCalledWith('copy')
  expect(document.querySelector('[data-copy-fallback]')).toBeNull()
})

test('copy button cleans up and reports failure when execCommand throws', async () => {
  setClipboard(vi.fn().mockRejectedValue(new Error('denied')))
  const execCommand = vi.fn().mockImplementation(() => {
    throw new Error('copy blocked')
  })
  setExecCommand(execCommand)
  const view = render(CopyButton, { props: { text: '推荐说法' } })

  await fireEvent.click(view.getByRole('button', { name: '复制' }))

  await waitFor(() => expect(view.getByText('复制失败，请重试')).toBeInTheDocument())
  expect(execCommand).toHaveBeenCalledWith('copy')
  expect(document.querySelector('[data-copy-fallback]')).toBeNull()
})
