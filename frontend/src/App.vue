<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import AppShell from './components/AppShell.vue'

type AppArea = 'login' | 'employee' | 'admin'

const route = useRoute()

const area = computed<AppArea>(() => {
  const routeArea = route.meta.area
  return routeArea === 'login' || routeArea === 'admin' || routeArea === 'employee'
    ? routeArea
    : 'employee'
})
</script>

<template>
  <AppShell :area="area">
    <RouterView />
  </AppShell>
</template>
