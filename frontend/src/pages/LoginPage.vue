<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { login } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const form = reactive({
  username: '',
  password: '',
})
const validationErrors = reactive({
  username: '',
  password: '',
})
const loginError = ref('')
const isSubmitting = ref(false)

function validateForm() {
  validationErrors.username = form.username.trim() ? '' : '请输入用户名'
  validationErrors.password = form.password ? '' : '请输入密码'
  return !validationErrors.username && !validationErrors.password
}

async function submitLogin() {
  loginError.value = ''

  if (!validateForm()) {
    return
  }

  isSubmitting.value = true
  try {
    const result = await login({
      username: form.username.trim(),
      password: form.password,
    })
    auth.setSession(result.access_token, result.user)
    await router.push(auth.defaultRoute)
  } catch (error) {
    const apiError = error as { code?: string; message?: string }
    loginError.value =
      apiError.code === 'account_disabled' && apiError.message
        ? apiError.message
        : '账号或密码错误，请重新输入'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <main class="page page-login">
    <form
      class="login-panel"
      data-testid="login-panel"
      style="width: 100%; max-width: 380px"
      @submit.prevent="submitLogin"
    >
      <h1>登录</h1>

      <label class="login-panel__field">
        <span>用户名</span>
        <input v-model="form.username" autocomplete="username" name="username" type="text" />
      </label>
      <p v-if="validationErrors.username" class="login-panel__error">
        {{ validationErrors.username }}
      </p>

      <label class="login-panel__field">
        <span>密码</span>
        <input
          v-model="form.password"
          autocomplete="current-password"
          name="password"
          type="password"
        />
      </label>
      <p v-if="validationErrors.password" class="login-panel__error">
        {{ validationErrors.password }}
      </p>

      <p v-if="loginError" class="login-panel__error" role="alert">{{ loginError }}</p>

      <button type="submit" :disabled="isSubmitting">
        {{ isSubmitting ? '登录中' : '登录' }}
      </button>
    </form>
  </main>
</template>

<style scoped>
.page-login {
  display: grid;
  min-height: 100vh;
  padding: 20px;
  place-items: center;
}

.login-panel {
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  box-shadow: 0 16px 40px rgb(15 23 42 / 8%);
  display: grid;
  gap: 12px;
  max-width: 380px;
  padding: 24px;
  width: 100%;
}

.login-panel h1 {
  font-size: 28px;
  line-height: 1.2;
  margin: 0 0 4px;
}

.login-panel__field {
  display: grid;
  gap: 6px;
}

.login-panel__field span {
  font-weight: 700;
}

.login-panel__field input {
  border: 1px solid #bcccdc;
  border-radius: 6px;
  font: inherit;
  min-height: 40px;
  min-width: 0;
  padding: 0 12px;
}

.login-panel__error {
  color: #be123c;
  font-size: 14px;
  margin: -4px 0 0;
}

.login-panel button {
  border: 0;
  border-radius: 6px;
  background: #1d4ed8;
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  min-height: 42px;
}

.login-panel button:disabled {
  cursor: wait;
  opacity: 0.7;
}
</style>
