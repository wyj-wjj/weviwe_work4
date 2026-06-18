<script setup lang="ts">
import EmployeeLayout from '../components/EmployeeLayout.vue'
</script>

<template>
  <EmployeeLayout>
    <section class="employee-home__intro">
      <h2>今日入口</h2>
      <p>选择一个模块继续查看已发布内容，或直接在上方输入问题检索标准话术。</p>
    </section>
  </EmployeeLayout>
</template>

<style scoped>
.employee-home__intro {
  color: #52606d;
}

.employee-home__intro h2 {
  color: #1f2933;
  font-size: 20px;
  margin: 0 0 8px;
}

.employee-home__intro p {
  margin: 0;
}
</style>
