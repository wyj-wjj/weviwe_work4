import { fireEvent, render, waitFor } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import { login } from '../src/api/auth'
import LoginPage from '../src/pages/LoginPage.vue'
import { createAppRouter } from '../src/router'
import { useAuthStore } from '../src/stores/auth'

vi.mock('../src/api/auth', () => ({
  login: vi.fn(),
}))

const mockedLogin = vi.mocked(login)

function renderLoginPage() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createAppRouter(createMemoryHistory())
  router.push('/login')

  return {
    ...render(LoginPage, {
      global: {
        plugins: [pinia, router],
      },
    }),
    router,
  }
}

beforeEach(() => {
  sessionStorage.clear()
  mockedLogin.mockReset()
})

test('login form blocks empty username or password and shows validation feedback', async () => {
  const { getByRole, getByText } = renderLoginPage()

  await fireEvent.click(getByRole('button', { name: '登录' }))

  expect(getByText('请输入用户名')).toBeInTheDocument()
  expect(getByText('请输入密码')).toBeInTheDocument()
  expect(mockedLogin).not.toHaveBeenCalled()
})

test('successful login stores user identity and routes to the correct default page', async () => {
  const { getByLabelText, getByRole, router } = renderLoginPage()
  const auth = useAuthStore()

  mockedLogin.mockResolvedValue({
    access_token: 'admin-token',
    token_type: 'bearer',
    user: {
      id: 1,
      username: 'admin',
      display_name: '管理员',
      account_type: 'admin',
      content_level: 'full',
    },
  })

  await fireEvent.update(getByLabelText('用户名'), 'admin')
  await fireEvent.update(getByLabelText('密码'), 'secret')
  await fireEvent.click(getByRole('button', { name: '登录' }))

  await waitFor(() => {
    expect(auth.token).toBe('admin-token')
    expect(router.currentRoute.value.path).toBe('/admin')
  })
})

test('invalid credentials show the generic login failure', async () => {
  const { getByLabelText, getByRole, getByText } = renderLoginPage()

  mockedLogin.mockRejectedValue({
    status: 401,
    code: 'auth_failed',
    message: 'disabled',
    details: null,
  })

  await fireEvent.update(getByLabelText('用户名'), 'disabled-user')
  await fireEvent.update(getByLabelText('密码'), 'wrong')
  await fireEvent.click(getByRole('button', { name: '登录' }))

  await waitFor(() => {
    expect(getByText('账号或密码错误，请重新输入')).toBeInTheDocument()
  })
})

test('disabled account login shows the backend account status message', async () => {
  const { getByLabelText, getByRole, getByText } = renderLoginPage()

  mockedLogin.mockRejectedValue({
    status: 403,
    code: 'account_disabled',
    message: '账号已被禁用，请联系管理员。',
    details: null,
  })

  await fireEvent.update(getByLabelText('用户名'), 'disabled-user')
  await fireEvent.update(getByLabelText('密码'), 'correct-password')
  await fireEvent.click(getByRole('button', { name: '登录' }))

  await waitFor(() => {
    expect(getByText('账号已被禁用，请联系管理员。')).toBeInTheDocument()
  })
})

test('login controls fit inside a mobile viewport without overlapping', () => {
  window.innerWidth = 375
  const { getByTestId } = renderLoginPage()

  expect(getByTestId('login-panel')).toHaveStyle({
    width: '100%',
    maxWidth: '380px',
  })
})
