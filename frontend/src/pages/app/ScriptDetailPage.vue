<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getScript, type ScriptDetail } from '../../api/content'
import AppState from '../../components/AppState.vue'
import CopyButton from '../../components/CopyButton.vue'
import EmployeeLayout from '../../components/EmployeeLayout.vue'
import { formatDateTime, permissionLabel } from '../../utils/format'

const route = useRoute()
const script = ref<ScriptDetail | null>(null)
const state = ref<'loading' | 'ready' | 'permission' | 'service'>('loading')

const isStandardScript = computed(() => script.value?.content_type === 'standard_script')
const recommendedSpeech = computed(() =>
  script.value && 'recommended_speech' in script.value ? (script.value.recommended_speech ?? '') : '',
)

onMounted(async () => {
  script.value = null
  state.value = 'loading'
  try {
    script.value = await getScript(String(route.params.contentId))
    state.value = 'ready'
  } catch (error) {
    const apiError = error as { status?: number }
    state.value = apiError.status === 403 ? 'permission' : 'service'
  }
})
</script>

<template>
  <EmployeeLayout>
    <AppState v-if="state === 'loading'" state="loading" />
    <AppState v-else-if="state === 'permission'" state="permission" />
    <AppState v-else-if="state === 'service'" state="service" />

    <article v-else-if="script" class="script-detail">
      <header>
        <h2>{{ script.title }}</h2>
        <p>
          <span>更新时间：{{ formatDateTime(script.updated_at) }}</span>
          <strong>{{ permissionLabel(script.permission_level) }}</strong>
        </p>
      </header>

      <template v-if="isStandardScript && 'recommended_speech' in script">
        <section>
          <h3>场景</h3>
          <p>{{ script.scene }}</p>
        </section>
        <section>
          <h3>推荐说法</h3>
          <p>{{ script.recommended_speech }}</p>
          <CopyButton label="复制推荐说法" :text="recommendedSpeech" />
        </section>
        <section>
          <h3>禁用说法</h3>
          <p>{{ script.forbidden_speech }}</p>
        </section>
        <section>
          <h3>注意事项</h3>
          <p>{{ script.notes }}</p>
        </section>
        <CopyButton label="复制完整条目" :text="script.copy_text" />
      </template>

      <template v-else-if="'body' in script">
        <section>
          <h3>精简要点</h3>
          <ul>
            <li v-for="point in script.summary_points" :key="point">{{ point }}</li>
          </ul>
        </section>
        <section>
          <h3>完整话术</h3>
          <p>{{ script.body }}</p>
        </section>
        <CopyButton label="复制完整话术" :text="script.copy_text" />
      </template>
    </article>
  </EmployeeLayout>
</template>

<style scoped>
.script-detail {
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  display: grid;
  gap: 18px;
  padding: 20px;
}

.script-detail h2 {
  font-size: 24px;
  margin: 0 0 10px;
}

.script-detail h3 {
  font-size: 17px;
  margin: 0 0 8px;
}

.script-detail p {
  line-height: 1.7;
  margin: 0;
}

.script-detail header p {
  color: #52606d;
  display: flex;
  gap: 10px;
}

.script-detail header strong {
  color: #1d4ed8;
}
</style>
