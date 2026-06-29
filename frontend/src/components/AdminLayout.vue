<script setup lang="ts">
import { RouterLink, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <main v-if="auth.isAdmin" class="admin-layout">
    <aside class="admin-layout__side">
      <h1>后台</h1>
      <nav aria-label="后台导航">
        <RouterLink to="/admin/contents">内容管理</RouterLink>
        <RouterLink to="/admin/quiz-questions">测验题管理</RouterLink>
        <RouterLink to="/admin/departments">部门管理</RouterLink>
        <RouterLink to="/admin/users">账号管理</RouterLink>
        <RouterLink to="/admin/missed-questions">未命中问题</RouterLink>
      </nav>
    </aside>

    <section class="admin-layout__main">
      <header class="admin-layout__header">
        <span>{{ auth.user?.display_name }}</span>
        <button type="button" @click="logout">退出登录</button>
      </header>
      <slot />
    </section>
  </main>
</template>

<style scoped>
.admin-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  min-height: 100vh;
}

.admin-layout__side {
  background: #111827;
  color: #ffffff;
  padding: 20px;
}

.admin-layout__side h1 {
  font-size: 22px;
  margin: 0 0 20px;
}

.admin-layout__side nav {
  display: grid;
  gap: 8px;
}

.admin-layout__side a {
  border-radius: 6px;
  color: #dbe4ff;
  padding: 10px 12px;
  text-decoration: none;
}

.admin-layout__side a:hover {
  background: #1f2937;
  color: #ffffff;
}

.admin-layout__main {
  min-width: 0;
  padding: 24px;
}

.admin-layout__header {
  align-items: center;
  border-bottom: 1px solid #d9e2ec;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-bottom: 24px;
  padding-bottom: 16px;
}

.admin-layout__header button {
  border: 1px solid #9aa5b1;
  border-radius: 6px;
  background: #ffffff;
  cursor: pointer;
  font: inherit;
  padding: 8px 12px;
}

@media (max-width: 768px) {
  .admin-layout {
    grid-template-columns: 1fr;
  }

  .admin-layout__side nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
