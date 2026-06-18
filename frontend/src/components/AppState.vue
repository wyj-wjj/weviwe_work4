<script setup lang="ts">
const props = defineProps<{
  state: 'empty' | 'loading' | 'permission' | 'service' | 'ai-unavailable'
  message?: string
}>()

const fallbackMessages = {
  empty: '暂无可查看的内容',
  loading: '加载中',
  permission: '无权查看该内容',
  service: '服务暂不可用，请稍后重试',
  'ai-unavailable': '智能问答暂不可用，请稍后重试',
}
</script>

<template>
  <section class="app-state" :data-state="state" role="status">
    <p>{{ props.message ?? fallbackMessages[state] }}</p>
  </section>
</template>

<style scoped>
.app-state {
  display: grid;
  min-height: 120px;
  place-items: center;
  padding: 24px;
  color: #52606d;
  text-align: center;
}

.app-state[data-state='permission'],
.app-state[data-state='service'],
.app-state[data-state='ai-unavailable'] {
  color: #9f1239;
}
</style>
