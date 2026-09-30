<template>
  <section class="page" data-module="flower">
    <header class="page-head">
      <div>
        <h2>花卉造景管理</h2>
        <p class="page-desc">按所在区域与花期阶段定位造景，并按最新换花规则计算从紧到松的换花优先级。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记花卉造景</button>
        <button class="btn" type="button" @click="exportRows">导出花卉造景清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>关键词</span>
        <input v-model="flowerStore.keyword" placeholder="编号、主题、品种或区域" />
      </label>
      <label class="filter-item">
        <span>所在区域</span>
        <select v-model="flowerStore.area">
          <option value="">全部区域</option>
          <option v-for="area in flowerStore.options.areas" :key="area" :value="area">{{ area }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>花期阶段</span>
        <select v-model="flowerStore.stage">
          <option value="">全部阶段</option>
          <option v-for="stage in stageOptions" :key="stage" :value="stage">{{ stage }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>每页片数</span>
        <select v-model.number="flowerStore.size" @change="applyFilters">
          <option :value="5">5 片</option>
          <option :value="10">10 片</option>
          <option :value="20">20 片</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div class="notice" :class="{ warning: flowerStore.total !== flowerStore.registeredTotal }">
      <div>
        当前口径筛出 <strong>{{ flowerStore.total }}</strong> 片；
        有效造景 <strong>{{ flowerStore.availableTotal }}</strong> 片，
        原始登记 <strong>{{ flowerStore.registeredTotal }}</strong> 条。
        重复登记已去重 <strong>{{ quality.duplicate_total }}</strong> 条，
        缺字段过滤 <strong>{{ quality.invalid_total }}</strong> 条。
      </div>
      <button v-if="showQualityDetails" class="link" type="button" @click="showQualityDetails = false">
        收起过滤说明
      </button>
      <button v-else class="link" type="button" @click="showQualityDetails = true">
        查看过滤说明
      </button>
    </div>

    <div v-if="showQualityDetails" class="quality-panel">
      <div v-if="quality.duplicates.length">
        <h4>重复登记，仅保留最新版本</h4>
        <ul>
          <li v-for="item in quality.duplicates" :key="`duplicate-${item.id}`">{{ item.reason }}</li>
        </ul>
      </div>
      <div v-if="quality.invalid.length">
        <h4>缺字段已过滤</h4>
        <ul>
          <li v-for="item in quality.invalid" :key="`invalid-${item.id}`">
            id={{ item.id }}（{{ item.造景编号 || '未填编号' }} {{ item.造景主题 }}）：{{ item.reason }}
          </li>
        </ul>
      </div>
      <p v-if="!quality.duplicates.length && !quality.invalid.length" class="muted">暂无重复或缺字段记录。</p>
    </div>

    <table class="data-table flower-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in flowerStore.rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <RouterLink
              v-if="column === '造景编号'"
              class="row-detail-link"
              :to="{ name: 'flower-detail', params: { id: row.id }, query: flowerStore.queryParams }"
              @click="flowerStore.saveScrollPosition()"
            >
              {{ row[column] }}
            </RouterLink>
            <span v-else>{{ displayValue(row[column]) }}</span>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="flowerStore.runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!flowerStore.rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            {{ flowerStore.loading ? '正在读取花卉造景…' : '当前条件下暂无有效花卉造景' }}
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot list-footer">
      <div class="pager">
        <button class="btn" type="button" :disabled="flowerStore.page <= 1" @click="goPage(flowerStore.page - 1)">
          上一页
        </button>
        <span>第 {{ flowerStore.page }} / {{ flowerStore.totalPages }} 页</span>
        <button
          class="btn"
          type="button"
          :disabled="flowerStore.page >= flowerStore.totalPages"
          @click="goPage(flowerStore.page + 1)"
        >
          下一页
        </button>
      </div>
      <span v-if="flowerStore.errorMessage" class="error-text">{{ flowerStore.errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useFlowerStore } from '@/stores/flower'

const route = useRoute()
const router = useRouter()
const flowerStore = useFlowerStore()
const showQualityDetails = ref(true)

const columns = [
  '造景编号',
  '造景主题',
  '所在区域',
  '花期阶段',
  '花卉品种',
  '景观面积',
  '花期起止',
  '换花周期',
  '换花优先级',
  '养护人员',
  '造景状态',
]
const actions = ['开始造景', '记录盛花', '安排换花']
const stageOptions = ['造景中', '盛花期', '凋谢期', '已换花']

const quality = computed(() => flowerStore.qualityOrEmpty)
const stats = computed(() => [
  { label: '原始登记', value: flowerStore.registeredTotal },
  { label: '有效造景', value: flowerStore.availableTotal },
  { label: '盛花期景观', value: quality.value.stage_counts['盛花期'] ?? 0 },
  { label: '凋谢期待换', value: quality.value.stage_counts['凋谢期'] ?? 0 },
])

function displayValue(value: unknown) {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

async function syncRouteQuery() {
  flowerStore.setFiltersFromQuery(route.query)
  await Promise.all([flowerStore.loadOptions(), flowerStore.loadRows()])
  await nextTick()
  flowerStore.restoreScrollPosition()
}

async function pushListQuery() {
  await router.push({ path: '/flower', query: flowerStore.queryParams })
  window.scrollTo({ top: 0 })
  await flowerStore.loadRows()
}

function applyFilters() {
  flowerStore.page = 1
  void pushListQuery()
}

function resetFilters() {
  flowerStore.keyword = ''
  flowerStore.area = ''
  flowerStore.stage = ''
  flowerStore.page = 1
  flowerStore.size = 5
  void pushListQuery()
}

function goPage(page: number) {
  flowerStore.page = page
  void pushListQuery()
}

function exportRows() {
  const query = new URLSearchParams()
  Object.entries(flowerStore.queryParams).forEach(([key, value]) => query.set(key, String(value)))
  window.open(`/api/flower/export?${query.toString()}`, '_blank')
}

function openCreate() {
  flowerStore.errorMessage = '花卉造景登记入口尚未接入审批流'
}

onMounted(syncRouteQuery)
</script>
