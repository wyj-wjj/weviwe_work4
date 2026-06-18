import {
  createRouter,
  createWebHistory,
  type RouterHistory,
  type RouteRecordRaw,
} from 'vue-router'

import AdminHomePage from '../pages/AdminHomePage.vue'
import AiAnswerPage from '../pages/app/AiAnswerPage.vue'
import EmployeeHomePage from '../pages/EmployeeHomePage.vue'
import LoginPage from '../pages/LoginPage.vue'
import MustReadDetailPage from '../pages/app/MustReadDetailPage.vue'
import MustReadListPage from '../pages/app/MustReadListPage.vue'
import QuizPage from '../pages/app/QuizPage.vue'
import ScriptDetailPage from '../pages/app/ScriptDetailPage.vue'
import ScriptsPage from '../pages/app/ScriptsPage.vue'
import { useAuthStore } from '../stores/auth'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/login',
  },
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: { area: 'login' },
  },
  {
    path: '/app',
    name: 'employee-home',
    component: EmployeeHomePage,
    meta: { area: 'employee', requiresAuth: true },
  },
  {
    path: '/app/must-reads',
    name: 'employee-must-reads',
    component: MustReadListPage,
    meta: { area: 'employee', requiresAuth: true },
  },
  {
    path: '/app/must-reads/:contentId',
    name: 'employee-must-read-detail',
    component: MustReadDetailPage,
    meta: { area: 'employee', requiresAuth: true },
  },
  {
    path: '/app/scripts',
    name: 'employee-scripts',
    component: ScriptsPage,
    meta: { area: 'employee', requiresAuth: true },
  },
  {
    path: '/app/scripts/:contentId',
    name: 'employee-script-detail',
    component: ScriptDetailPage,
    meta: { area: 'employee', requiresAuth: true },
  },
  {
    path: '/app/quiz',
    name: 'employee-quiz',
    component: QuizPage,
    meta: { area: 'employee', requiresAuth: true },
  },
  {
    path: '/app/ask',
    name: 'employee-ai-answer',
    component: AiAnswerPage,
    meta: { area: 'employee', requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'admin-home',
    component: AdminHomePage,
    meta: { area: 'admin', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/contents',
    name: 'admin-contents',
    component: AdminHomePage,
    meta: { area: 'admin', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/quiz-questions',
    name: 'admin-quiz-questions',
    component: AdminHomePage,
    meta: { area: 'admin', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: AdminHomePage,
    meta: { area: 'admin', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/missed-questions',
    name: 'admin-missed-questions',
    component: AdminHomePage,
    meta: { area: 'admin', requiresAuth: true, requiresAdmin: true },
  },
]

export function createAppRouter(history: RouterHistory = createWebHistory()) {
  const router = createRouter({
    history,
    routes,
  })

  router.beforeEach((to) => {
    const auth = useAuthStore()

    if (to.name === 'login' && auth.isAuthenticated) {
      return auth.defaultRoute
    }

    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return {
        name: 'login',
        query: {
          redirect: to.fullPath,
        },
      }
    }

    if (to.meta.requiresAdmin && !auth.isAdmin) {
      return '/app'
    }

    return true
  })

  return router
}

export const router = createAppRouter()
