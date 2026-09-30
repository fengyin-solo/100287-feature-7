<template>
  <section class="page" data-module="flower-detail">
    <header class="page-head">
      <div>
        <h2>花卉造景明细</h2>
        <p class="page-desc">单幅造景的花期阶段、换花周期与优先级与列表页按同一套规矩计算。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表（停在原位置）</button>
      </div>
    </header>

    <div v-if="errorMessage" class="notice error">
      <span>{{ errorMessage }}</span>
      <button class="btn" type="button" @click="goBack">返回列表</button>
    </div>

    <template v-else-if="entry">
      <div v-if="entry.已归档" class="notice warn">
        该造景编号因重复登记被合并、或因缺少景观面积/花卉品种被过滤，不在当前在册列表中；下方为原始登记内容。
      </div>

      <div class="detail-head">
        <h3>{{ entry.造景编号 }} · {{ entry.造景主题 }}</h3>
        <span v-if="!entry.已归档" class="badge" :class="`badge-${tierClass(entry.换花优先级)}`">{{ entry.换花优先级 }}</span>
      </div>

      <table class="data-table detail-table">
        <tbody>
          <tr v-for="field in displayFields" :key="field.key">
            <th>{{ field.label }}</th>
            <td>{{ formatValue(field.key) }}</td>
          </tr>
        </tbody>
      </table>

      <div v-if="!entry.已归档" class="detail-actions">
        <button class="btn primary" type="button" :disabled="changing" @click="markChanged">
          {{ changing ? '提交中…' : '安排换花（按当前规矩重排优先级）' }}
        </button>
        <span v-if="actionMessage" class="rules-note">{{ actionMessage }}</span>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useFlowerStore, type FlowerRow } from '@/stores/flower'

const route = useRoute()
const router = useRouter()
const flowerStore = useFlowerStore()

const entry = ref<FlowerRow | null>(null)
const errorMessage = ref('')
const changing = ref(false)
const actionMessage = ref('')

const displayFields = [
  { key: '所在区域', label: '所在区域' },
  { key: '花卉品种', label: '花卉品种' },
  { key: '景观面积', label: '景观面积（㎡）' },
  { key: '花期起', label: '花期起' },
  { key: '花期止', label: '花期止' },
  { key: '花期阶段', label: '当前花期阶段' },
  { key: '换花周期天数', label: '本阶段换花周期（天）' },
  { key: '上次换花日', label: '上次换花日' },
  { key: '下次换花日', label: '预计下次换花日' },
  { key: '剩余天数', label: '距下次换花' },
  { key: '换花优先级', label: '换花优先级' },
  { key: '造景状态', label: '台账状态' },
  { key: '养护人员', label: '养护人员' },
  { key: '登记时间', label: '本版登记时间' },
]

const entryId = computed(() => Number(route.params.id))

function tierClass(tier: string): string {
  return { 已逾期: 'overdue', 紧急: 'urgent', 偏紧: 'tight', 正常: 'normal', 宽松: 'loose' }[tier] ?? 'normal'
}

function formatValue(key: string) {
  if (!entry.value) return '—'
  if (key === '剩余天数') {
    const days = Number(entry.value.剩余天数)
    return Number.isNaN(days) ? '—' : days < 0 ? `已逾期 ${-days} 天` : `还剩 ${days} 天`
  }
  return entry.value[key] ?? '—'
}

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`/api/flower/${entryId.value}`)
    if (response.status === 404) {
      throw new Error(`花卉造景 ${entryId.value} 不存在或已归档`)
    }
    entry.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '明细读取失败'
  }
}

async function markChanged() {
  changing.value = true
  actionMessage.value = ''
  try {
    await flowerStore.markChanged(entryId.value)
    actionMessage.value = '已安排换花，返回列表即可看到重排后的位置'
    await load()
  } catch (error) {
    actionMessage.value = error instanceof Error ? error.message : '安排换花失败'
  } finally {
    changing.value = false
  }
}

function goBack() {
  // 返回列表：条件与页码一直锁在共享 query 里，URL 也带着，直接回 /flower 即可
  void router.push({
    name: 'flower',
    query: {
      ...(flowerStore.query.region ? { region: flowerStore.query.region } : {}),
      ...(flowerStore.query.phase ? { phase: flowerStore.query.phase } : {}),
      ...(flowerStore.query.priority ? { priority: flowerStore.query.priority } : {}),
      ...(flowerStore.query.keyword ? { keyword: flowerStore.query.keyword } : {}),
      ...(flowerStore.query.page > 1 ? { page: String(flowerStore.query.page) } : {}),
    },
  })
}

onMounted(() => {
  window.scrollTo(0, 0)
  void load()
})
</script>
