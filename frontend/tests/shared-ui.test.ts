import { fireEvent, render, waitFor } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import AdminHomePage from '../src/pages/AdminHomePage.vue'
import EmployeeHomePage from '../src/pages/EmployeeHomePage.vue'
import { createAppRouter } from '../src/router'
import { useAuthStore, type AuthUser } from '../src/stores/auth'
import AppState from '../src/components/AppState.vue'
import CopyButton from '../src/components/CopyButton.vue'

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

test('copy button shows success and recoverable failure feedback', async () => {
  const originalClipboard = navigator.clipboard

  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: {
      writeText: vi.fn().mockResolvedValue(undefined),
    },
  })

  const { getByRole, getByText, rerender } = render(CopyButton, {
    props: {
      text: '推荐说法',
    },
  })

  await fireEvent.click(getByRole('button', { name: '复制' }))
  await waitFor(() => {
    expect(getByText('已复制')).toBeInTheDocument()
  })

  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: {
      writeText: vi.fn().mockRejectedValue(new Error('denied')),
    },
  })
  await rerender({ text: '推荐说法' })
  await fireEvent.click(getByRole('button', { name: '复制' }))

  await waitFor(() => {
    expect(getByText('复制失败，请重试')).toBeInTheDocument()
  })

  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: originalClipboard,
  })
})
