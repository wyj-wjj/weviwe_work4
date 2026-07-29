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
    <section class="login-intro" aria-label="WeView">
      <div class="login-intro__brand">
        <span class="login-intro__mark">W</span>
        <div>
          <p>WeView</p>
          <h1>企业话术中枢</h1>
        </div>
      </div>

      <p class="login-intro__copy">让统一口径沉淀为稳定、可追溯、可检索的日常工作台。</p>

      <div class="login-intro__board" aria-hidden="true">
        <div class="login-intro__line login-intro__line--wide"></div>
        <div class="login-intro__line"></div>
        <div class="login-intro__grid">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </section>

    <form
      class="login-panel"
      data-testid="login-panel"
      style="width: 100%; max-width: 380px"
      @submit.prevent="submitLogin"
    >
      <header class="login-panel__header">
        <p>安全登录</p>
        <h2>欢迎回来</h2>
      </header>

      <label class="login-panel__field">
        <span>用户名</span>
        <input
          v-model="form.username"
          autocomplete="username"
          name="username"
          placeholder="请输入用户名"
          type="text"
        />
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
          placeholder="请输入密码"
          type="password"
        />
      </label>
      <p v-if="validationErrors.password" class="login-panel__error">
        {{ validationErrors.password }}
      </p>

      <p v-if="loginError" class="login-panel__error" role="alert">{{ loginError }}</p>

      <button type="submit" :disabled="isSubmitting" :aria-busy="isSubmitting">
        {{ isSubmitting ? '登录中' : '登录' }}
      </button>
    </form>
  </main>
</template>

<style scoped>
.page-login {
  align-items: center;
  background:
    linear-gradient(118deg, #f8fafc 0%, #f8fafc 48%, #eaf3ee 48%, #eaf3ee 100%);
  color: #16202a;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 380px);
  gap: clamp(28px, 6vw, 76px);
  min-height: 100vh;
  max-width: none;
  overflow: hidden;
  padding: clamp(28px, 6vw, 72px);
  position: relative;
  width: 100%;
}

.page-login::before,
.page-login::after {
  content: '';
  pointer-events: none;
  position: absolute;
}

.page-login::before {
  background: #dce7f2;
  height: 1px;
  left: 0;
  top: 19%;
  width: 100%;
}

.page-login::after {
  background: #d7e5dc;
  bottom: 12%;
  height: 1px;
  left: 0;
  width: 100%;
}

.login-intro,
.login-panel {
  position: relative;
  z-index: 1;
}

.login-intro {
  display: grid;
  gap: 28px;
  justify-self: end;
  max-width: 560px;
  width: 100%;
}

.login-intro__brand {
  align-items: center;
  display: flex;
  gap: 16px;
}

.login-intro__mark {
  align-items: center;
  background: #18324a;
  border: 1px solid #0f2538;
  border-radius: 8px;
  color: #ffffff;
  display: inline-flex;
  flex: 0 0 auto;
  font-size: 28px;
  font-weight: 800;
  height: 58px;
  justify-content: center;
  width: 58px;
}

.login-intro__brand p,
.login-panel__header p {
  color: #2f6f63;
  font-size: 13px;
  font-weight: 800;
  margin: 0 0 6px;
}

.login-intro__brand h1,
.login-panel__header h2 {
  letter-spacing: 0;
  line-height: 1.1;
  margin: 0;
}

.login-intro__brand h1 {
  font-size: clamp(34px, 5vw, 56px);
}

.login-intro__copy {
  color: #445668;
  font-size: clamp(18px, 2.2vw, 22px);
  line-height: 1.7;
  margin: 0;
  max-width: 470px;
}

.login-intro__board {
  background: #ffffff;
  border: 1px solid #d5e0ea;
  border-radius: 8px;
  box-shadow: 0 24px 70px rgb(22 32 42 / 12%);
  display: grid;
  gap: 14px;
  max-width: 440px;
  padding: 22px;
}

.login-intro__line {
  background: #d8e2eb;
  border-radius: 4px;
  height: 10px;
  width: 54%;
}

.login-intro__line--wide {
  background: #bfd7d0;
  width: 78%;
}

.login-intro__grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 8px;
}

.login-intro__grid span {
  background: #f3f6f9;
  border: 1px solid #dde6ee;
  border-radius: 8px;
  min-height: 74px;
}

.login-intro__grid span:nth-child(2) {
  background: #f7f3e8;
  border-color: #e6dbc0;
}

.login-intro__grid span:nth-child(3) {
  background: #edf6f2;
  border-color: #cfe4da;
}

.login-panel {
  background: #ffffff;
  border: 1px solid #d8e1ea;
  border-radius: 8px;
  box-shadow: 0 24px 70px rgb(22 32 42 / 14%);
  display: grid;
  gap: 14px;
  max-width: 380px;
  padding: 28px;
  width: 100%;
}

.login-panel__header {
  margin-bottom: 6px;
}

.login-panel__header h2 {
  color: #16202a;
  font-size: 28px;
}

.login-panel__field {
  display: grid;
  gap: 8px;
}

.login-panel__field span {
  color: #324658;
  font-size: 14px;
  font-weight: 700;
}

.login-panel__field input {
  background: #f8fafc;
  border: 1px solid #c7d4df;
  border-radius: 8px;
  color: #16202a;
  font: inherit;
  min-height: 46px;
  min-width: 0;
  padding: 0 14px;
  width: 100%;
}

.login-panel__field input:focus {
  background: #ffffff;
  border-color: #2f6f63;
  box-shadow: 0 0 0 3px rgb(47 111 99 / 14%);
  outline: none;
}

.login-panel__field input::placeholder {
  color: #8796a5;
}

.login-panel__error {
  background: #fff1f2;
  border: 1px solid #fecdd3;
  border-radius: 6px;
  color: #be123c;
  font-size: 14px;
  margin: -4px 0 0;
  padding: 8px 10px;
}

.login-panel button {
  border: 0;
  border-radius: 8px;
  background: #18324a;
  box-shadow: 0 12px 24px rgb(24 50 74 / 18%);
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  min-height: 46px;
  transition:
    background 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.login-panel button:hover:not(:disabled) {
  background: #244b6d;
  box-shadow: 0 16px 30px rgb(24 50 74 / 22%);
  transform: translateY(-1px);
}

.login-panel button:disabled {
  cursor: wait;
  opacity: 0.7;
}

@media (max-width: 780px) {
  .page-login {
    grid-template-columns: 1fr;
    padding: 24px 16px;
  }

  .page-login::before,
  .page-login::after {
    display: none;
  }

  .login-intro {
    gap: 18px;
    justify-self: center;
    max-width: 380px;
  }

  .login-intro__brand {
    align-items: flex-start;
  }

  .login-intro__mark {
    font-size: 22px;
    height: 48px;
    width: 48px;
  }

  .login-intro__brand h1 {
    font-size: 32px;
  }

  .login-intro__copy {
    font-size: 16px;
  }

  .login-intro__board {
    display: none;
  }

  .login-panel {
    justify-self: center;
    padding: 24px;
  }
}
</style>
