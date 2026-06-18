import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../src/stores/auth'

const adminUser = {
  id: 1,
  username: 'admin',
  display_name: '管理员',
  account_type: 'admin' as const,
  content_level: 'full' as const,
}

beforeEach(() => {
  sessionStorage.clear()
})

test('auth state persists token and user identity during the browser session', () => {
  setActivePinia(createPinia())
  const auth = useAuthStore()

  auth.setSession('access-token', adminUser)

  setActivePinia(createPinia())
  const restored = useAuthStore()

  expect(restored.token).toBe('access-token')
  expect(restored.user?.username).toBe('admin')
  expect(restored.accountType).toBe('admin')
  expect(restored.contentLevel).toBe('full')
  expect(restored.isAuthenticated).toBe(true)
})

test('logout clears token and user data from memory and session storage', () => {
  setActivePinia(createPinia())
  const auth = useAuthStore()

  auth.setSession('access-token', adminUser)
  auth.logout()

  expect(auth.token).toBeNull()
  expect(auth.user).toBeNull()
  expect(auth.isAuthenticated).toBe(false)
  expect(sessionStorage.getItem('weview.auth')).toBeNull()
})
