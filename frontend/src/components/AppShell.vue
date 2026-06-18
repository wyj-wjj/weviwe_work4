<script setup lang="ts">
defineProps<{
  area: 'login' | 'employee' | 'admin'
}>()
</script>

<template>
  <section
    class="app-shell"
    :data-area="area"
    data-testid="app-shell"
    style="max-width: 100vw; overflow-x: hidden"
  >
    <slot />
  </section>
</template>

<style scoped>
.app-shell {
  width: 100%;
  min-height: 100vh;
  background: #f7f8fa;
  color: #1f2933;
}

.app-shell[data-area='admin'] {
  background: #f3f4f6;
}

.app-shell[data-area='login'] {
  display: grid;
  place-items: center;
  padding: 24px;
}
</style>
