import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { configureApiAuth } from './api/client'
import { router } from './router'
import { useAuthStore } from './stores/auth'
import './styles/base.css'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)

const auth = useAuthStore()
configureApiAuth({
  getToken: () => auth.token,
  onUnauthorized: () => {
    auth.clearSession()
    router.push('/login')
  },
})

app.use(router).mount('#app')
