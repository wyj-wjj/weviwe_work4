<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  text: string
  label?: string
}>()

const feedback = ref('')

function fallbackCopy(text: string): boolean {
  const activeElement = document.activeElement instanceof HTMLElement
    ? document.activeElement
    : null
  const selection = window.getSelection()
  const savedRanges = selection
    ? Array.from(
        { length: selection.rangeCount },
        (_, index) => selection.getRangeAt(index).cloneRange(),
      )
    : []
  const textarea = document.createElement('textarea')
  textarea.dataset.copyFallback = 'true'
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '0'
  document.body.appendChild(textarea)

  try {
    textarea.focus()
    textarea.select()
    return typeof document.execCommand === 'function' && document.execCommand('copy')
  } catch {
    return false
  } finally {
    textarea.remove()

    try {
      activeElement?.focus({ preventScroll: true })
    } catch {
      // The previous focus target may no longer be focusable.
    }

    if (selection) {
      try {
        selection.removeAllRanges()
        savedRanges.forEach((range) => selection.addRange(range))
      } catch {
        // The selected nodes may have been removed while the copy attempt ran.
      }
    }
  }
}

async function copyText() {
  feedback.value = ''

  try {
    if (!navigator.clipboard?.writeText) {
      throw new Error('Clipboard API unavailable')
    }
    await navigator.clipboard.writeText(props.text)
    feedback.value = '已复制'
  } catch {
    feedback.value = fallbackCopy(props.text) ? '已复制' : '复制失败，请重试'
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
