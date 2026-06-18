import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import { createAppRouter } from '../src/router'
import { useAuthStore } from '../src/stores/auth'

test('login, employee app, and admin app routes resolve to distinct route records', async () => {
  const router = createAppRouter()

  const login = router.resolve('/login')
  const employeeApp = router.resolve('/app')
  const adminApp = router.resolve('/admin')

  expect(login.name).toBe('login')
  expect(employeeApp.name).toBe('employee-home')
  expect(adminApp.name).toBe('admin-home')
  expect(new Set([login.name, employeeApp.name, adminApp.name]).size).toBe(3)
})

test('unauthenticated users are redirected from the employee app to login', async () => {
  setActivePinia(createPinia())
  const router = createAppRouter(createMemoryHistory())

  await router.push('/app')

  expect(router.currentRoute.value.name).toBe('login')
  expect(router.currentRoute.value.query.redirect).toBe('/app')
})

test('non-admin users are blocked from the admin app while admins can enter', async () => {
  setActivePinia(createPinia())
  const router = createAppRouter(createMemoryHistory())
  const auth = useAuthStore()

  auth.setSession('employee-token', {
    id: 2,
    username: 'full_user',
    display_name: '完整权限员工',
    account_type: 'full_user',
    content_level: 'full',
  })

  await router.push('/admin')
  expect(router.currentRoute.value.path).toBe('/app')

  auth.setSession('admin-token', {
    id: 1,
    username: 'admin',
    display_name: '管理员',
    account_type: 'admin',
    content_level: 'full',
  })

  await router.push('/admin')
  expect(router.currentRoute.value.name).toBe('admin-home')
})
