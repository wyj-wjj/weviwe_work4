<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  text: string
  label?: string
}>()

const feedback = ref('')

async function copyText() {
  feedback.value = ''

  try {
    await navigator.clipboard.writeText(props.text)
    feedback.value = '已复制'
  } catch {
    feedback.value = '复制失败，请重试'
  }
}
</script>

<template>
  <span class="copy-action">
    <button class="copy-action__button" type="button" @click="copyText">
      {{ label ?? '复制' }}
    </button>
    <span v-if="feedback" class="copy-action__feedback" role="status">{{ feedback }}</span>
  </span>
</template>

<style scoped>
.copy-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.copy-action__button {
  border: 1px solid #9aa5b1;
  border-radius: 6px;
  background: #ffffff;
  color: #1f2933;
  cursor: pointer;
  font: inherit;
  padding: 7px 12px;
}

.copy-action__button:hover {
  border-color: #3b82f6;
  color: #1d4ed8;
}

.copy-action__feedback {
  color: #52606d;
  font-size: 13px;
}
</style>
