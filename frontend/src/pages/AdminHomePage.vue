<script setup lang="ts">
import AdminLayout from '../components/AdminLayout.vue'
</script>

<template>
  <AdminLayout>
    <section class="admin-home__intro">
      <h2>后台首页</h2>
      <p>请选择左侧模块维护内容与账号。</p>
    </section>
  </AdminLayout>
</template>

<style scoped>
.admin-home__intro {
  color: #52606d;
}

.admin-home__intro h2 {
  color: #1f2933;
  font-size: 22px;
  margin: 0 0 8px;
}

.admin-home__intro p {
  margin: 0;
}
</style>
