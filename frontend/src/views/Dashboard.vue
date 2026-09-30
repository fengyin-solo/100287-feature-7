<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>

    <!-- 花卉换花快查：与花卉造景列表页共用同一个 store，同条件下取到的是同一份结果 -->
    <section class="quick-panel">
      <header class="quick-head">
        <div>
          <h3>花卉换花快查</h3>
          <p class="page-desc">在概览页选定区域或花期阶段，结果与「花卉造景」列表页完全一致（同一份缓存，规矩更新后同步重算）。</p>
        </div>
        <RouterLink class="btn" :to="flowerLink">带条件去列表页查看 →</RouterLink>
      </header>
      <div class="filter-bar">
        <label class="filter-item">
          <span>所在区域</span>
          <select v-model="quickRegion">
            <option value="">全部区域</option>
            <option v-for="region in meta?.regions ?? []" :key="region" :value="region">{{ region }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>花期阶段</span>
          <select v-model="quickPhase">
            <option value="">全部阶段</option>
            <option v-for="phase in meta?.phases ?? []" :key="phase" :value="phase">{{ phase }}</option>
          </select>
        </label>
      </div>
      <table class="data-table">
        <thead>
          <tr><th>造景编号</th><th>所在区域</th><th>花期阶段</th><th>下次换花日</th><th>剩余天数</th><th>换花优先级</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in quickRows" :key="String(row.id)">
            <td>
              <RouterLink class="link" :to="{ name: 'flower-detail', params: { id: row.id } }">{{ row.造景编号 }}</RouterLink>
            </td>
            <td>{{ row.所在区域 }}</td>
            <td>{{ row.花期阶段 }}</td>
            <td>{{ row.下次换花日 }}</td>
            <td :class="{ 'warn-num': row.剩余天数 <= 3 }">
              {{ row.剩余天数 < 0 ? `逾期 ${-row.剩余天数} 天` : `剩 ${row.剩余天数} 天` }}
            </td>
            <td><span class="badge" :class="`badge-${tierClass(row.换花优先级)}`">{{ row.换花优先级 }}</span></td>
          </tr>
          <tr v-if="!quickRows.length">
            <td colspan="6" class="empty-state">当前条件下暂无在册造景</td>
          </tr>
        </tbody>
      </table>
      <p class="quick-foot">
        命中 {{ quickResult?.total ?? 0 }} 片（只展示最紧的前 {{ quickQuery.size }} 片），
        登记 {{ quickResult?.summary.登记总条数 ?? 0 }} 条 · 合并重复
        {{ quickResult?.summary.重复合并条数 ?? 0 }} 条 · 过滤缺字段
        {{ quickResult?.summary.缺字段过滤条数 ?? 0 }} 条
      </p>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { fetchJson } from '@/api/client'
import { useFlowerStore, type FlowerQuery, type ListResult, type Meta } from '@/stores/flower'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])

const flowerStore = useFlowerStore()
const meta = ref<Meta | null>(null)
const quickResult = ref<ListResult | null>(null)

// 快查条件同步进共享 store：从这里跳列表页时，列表页直接沿用，取到同一份
const quickRegion = computed({
  get: () => flowerStore.query.region,
  set: (value: string) => flowerStore.setQuery({ region: value }),
})
const quickPhase = computed({
  get: () => flowerStore.query.phase,
  set: (value: string) => flowerStore.setQuery({ phase: value }),
})
// 快查固定展示最紧的前 5 片
const quickQuery = computed<FlowerQuery>(() => ({
  ...flowerStore.query,
  priority: '',
  keyword: '',
  page: 1,
  size: 5,
}))
const quickRows = computed(() => quickResult.value?.items ?? [])

const flowerLink = computed(() => ({
  name: 'flower',
  query: {
    ...(quickRegion.value ? { region: quickRegion.value } : {}),
    ...(quickPhase.value ? { phase: quickPhase.value } : {}),
  },
}))

function tierClass(tier: string): string {
  return { 已逾期: 'overdue', 紧急: 'urgent', 偏紧: 'tight', 正常: 'normal', 宽松: 'loose' }[tier] ?? 'normal'
}

async function loadQuick() {
  try {
    meta.value = await flowerStore.fetchMeta()
    quickResult.value = await flowerStore.fetchList(quickQuery.value)
  } catch {
    quickResult.value = null
  }
}

watch(quickQuery, () => {
  void loadQuick()
}, { deep: true })

onMounted(async () => {
  void loadQuick()
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{ label: '业务模块', value: 0 }, { label: '今日新增', value: 0 }]
    moduleRows.value = []
  }
})
</script>
