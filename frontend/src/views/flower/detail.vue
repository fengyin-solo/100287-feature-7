<template>
  <section class="page detail-page" data-module="flower-detail">
    <header class="page-head">
      <div>
        <h2>花卉造景明细</h2>
        <p class="page-desc">查看单幅造景的区域、花期与换花优先级；返回列表时保留筛选条件、页码和滚动位置。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" :to="listPath">返回列表</RouterLink>
      </div>
    </header>

    <div v-if="errorMessage" class="notice warning">{{ errorMessage }}</div>

    <article v-if="entry" class="detail-card">
      <div class="detail-title-row">
        <div>
          <span class="detail-code">{{ entry.造景编号 }}</span>
          <h3>{{ entry.造景主题 }}</h3>
        </div>
        <span class="status-badge">{{ entry.花期阶段 }}</span>
      </div>

      <dl class="detail-grid">
        <div v-for="field in fields" :key="field.key" class="detail-item">
          <dt>{{ field.label }}</dt>
          <dd>{{ displayValue(fieldValue(entry, field.key)) }}</dd>
        </div>
      </dl>

      <div class="detail-actions">
        <button
          v-for="action in actions"
          :key="action"
          class="btn"
          type="button"
          @click="runAction(action)"
        >
          {{ action }}
        </button>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useFlowerStore, type FlowerRow } from '@/stores/flower'

type DetailField = {
  key: keyof FlowerRow | '换花周期(天)'
  label: string
}

const route = useRoute()
const router = useRouter()
const flowerStore = useFlowerStore()

const entry = ref<FlowerRow | null>(null)
const errorMessage = ref('')
const actions = ['开始造景', '记录盛花', '安排换花']
const fields: DetailField[] = [
  { key: '所在区域', label: '所在区域' },
  { key: '花期阶段', label: '花期阶段' },
  { key: '花期起止', label: '花期起止' },
  { key: '换花周期', label: '换花周期' },
  { key: '换花周期(天)', label: '换算周期' },
  { key: '换花优先级', label: '换花优先级' },
  { key: '花卉品种', label: '花卉品种' },
  { key: '景观面积', label: '景观面积' },
  { key: '养护人员', label: '养护人员' },
  { key: '造景状态', label: '造景状态' },
]

const listPath = computed(() => ({ path: '/flower', query: flowerStore.queryParams }))

function displayValue(value: unknown) {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function fieldValue(row: FlowerRow, key: DetailField['key']) {
  if (key === '换花周期(天)') return row['换花周期(天)']
  return row[key]
}

async function loadEntry() {
  errorMessage.value = ''
  try {
    const response = await request(`/api/flower/${route.params.id}`)
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null
      throw new Error(payload?.detail || '花卉造景明细读取失败')
    }
    entry.value = (await response.json()) as FlowerRow
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '花卉造景明细读取失败'
  }
}

async function runAction(action: string) {
  if (!entry.value) return
  errorMessage.value = ''
  try {
    const response = await request(`/api/flower/${entry.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json()) as { ok?: boolean; message?: string }
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message || '花卉造景动作未生效，请稍后重试')
    }
    await loadEntry()
    await flowerStore.loadRows()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '花卉造景操作失败'
  }
}

function backToList() {
  void router.push(listPath.value)
}

onMounted(() => {
  flowerStore.setFiltersFromQuery(route.query)
  void loadEntry()
})
defineExpose({ backToList })
</script>
