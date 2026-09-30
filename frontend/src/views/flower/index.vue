<template>
  <section class="page" data-module="flower">
    <header class="page-head">
      <div>
        <h2>花卉造景管理</h2>
        <p class="page-desc">按所在区域与花期阶段定位造景，列表始终按换花周期从紧到松排列；重复登记只留最新版，缺面积/品种的先过滤并逐条说明。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记花卉造景</button>
        <button class="btn" type="button" @click="openRules">调整换花规矩</button>
        <button class="btn" type="button" @click="exportRows">导出当前筛选</button>
      </div>
    </header>

    <!-- 对账横幅：筛出来的片数与造景总数对不上时，一眼能看出差在哪 -->
    <div class="recon-bar">
      <div class="recon-main">
        <span>登记总数 <strong>{{ summary?.登记总条数 ?? '—' }}</strong></span>
        <span>重复合并 <strong>{{ summary?.重复合并条数 ?? '—' }}</strong></span>
        <span>缺字段过滤 <strong :class="{ 'warn-num': (summary?.缺字段过滤条数 ?? 0) > 0 }">{{ summary?.缺字段过滤条数 ?? '—' }}</strong></span>
        <span>在册 <strong>{{ summary?.在册片数 ?? '—' }}</strong></span>
        <span class="recon-current">当前筛选命中 <strong>{{ result?.total ?? '—' }}</strong> 片 / 本页 {{ summary?.本页片数 ?? 0 }} 片</span>
      </div>
      <div class="recon-links">
        <button v-if="(summary?.重复合并条数 ?? 0) > 0" class="link" type="button" @click="showMerged = !showMerged">
          {{ showMerged ? '收起' : '查看' }}重复合并明细
        </button>
        <button v-if="(summary?.缺字段过滤条数 ?? 0) > 0" class="link" type="button" @click="showFiltered = !showFiltered">
          {{ showFiltered ? '收起' : '查看' }}缺字段过滤明细（{{ summary?.缺字段过滤条数 }}）
        </button>
        <span v-if="summary?.规矩更新时间" class="rules-note">规矩更新于 {{ summary.规矩更新时间 }}</span>
      </div>
    </div>

    <ul v-if="showMerged && summary" class="detail-panel">
      <li v-for="(item, idx) in summary.重复合并明细" :key="`m-${idx}`">
        <strong>{{ item.造景编号 }}</strong>：保留 {{ item.保留版本 }}，合并旧版 {{ item.合并版本 }}
      </li>
    </ul>
    <ul v-if="showFiltered && summary" class="detail-panel warn">
      <li v-for="item in summary.缺字段过滤明细" :key="`f-${item.id ?? item.造景编号}`">
        <strong>{{ item.造景编号 ?? `id=${item.id}` }}</strong>
        （{{ item.造景主题 || '无主题' }}）：{{ item.原因 }}，登记时间 {{ item.登记时间 || '未知' }}
      </li>
    </ul>

    <div v-if="recomputeNotice" class="notice success">
      <span>{{ recomputeNotice }}</span>
      <button class="link" type="button" @click="recomputeNotice = ''">知道了</button>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>所在区域</span>
        <select v-model="draft.region">
          <option value="">全部区域</option>
          <option v-for="region in meta?.regions ?? []" :key="region" :value="region">{{ region }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>花期阶段</span>
        <select v-model="draft.phase">
          <option value="">全部阶段</option>
          <option v-for="phase in meta?.phases ?? []" :key="phase" :value="phase">{{ phase }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>换花优先级</span>
        <select v-model="draft.priority">
          <option value="">全部优先级</option>
          <option v-for="tier in meta?.priorities ?? []" :key="tier" :value="tier">{{ tier }}</option>
        </select>
      </label>
      <label class="filter-item grow">
        <span>关键词（编号 / 主题 / 品种）</span>
        <input v-model="draft.keyword" placeholder="如 FLOW-0001、月季" />
      </label>
      <button class="btn primary" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th>造景编号</th>
          <th>造景主题</th>
          <th>所在区域</th>
          <th>花卉品种</th>
          <th>景观面积(㎡)</th>
          <th>花期起止</th>
          <th>花期阶段</th>
          <th>周期(天)</th>
          <th>下次换花日</th>
          <th>剩余天数</th>
          <th>换花优先级</th>
          <th>养护人员</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="`priority-${tierClass(row.换花优先级)}`">
          <td><RouterLink class="link" :to="detailLink(row.id)">{{ row.造景编号 }}</RouterLink></td>
          <td>{{ row.造景主题 }}</td>
          <td>{{ row.所在区域 }}</td>
          <td>{{ row.花卉品种 }}</td>
          <td>{{ row.景观面积 }}</td>
          <td>{{ row.花期起 }} ~ {{ row.花期止 }}</td>
          <td><span class="tag">{{ row.花期阶段 }}</span></td>
          <td>{{ row.换花周期天数 }}</td>
          <td>{{ row.下次换花日 }}</td>
          <td :class="{ 'warn-num': row.剩余天数 <= 3 }">
            {{ row.剩余天数 < 0 ? `逾期 ${-row.剩余天数} 天` : `剩 ${row.剩余天数} 天` }}
          </td>
          <td><span class="badge" :class="`badge-${tierClass(row.换花优先级)}`">{{ row.换花优先级 }}</span></td>
          <td>{{ row.养护人员 || '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="markChanged(row)">安排换花</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="13" class="empty-state">当前条件下没有在册造景，可放宽区域或花期阶段再查</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>
        共 {{ result?.total ?? 0 }} 片
        <template v-if="hasActiveFilter">（已锁定筛选：{{ activeFilterText }}）</template>
      </span>
      <div class="pager">
        <button class="btn" type="button" :disabled="storeQuery.page <= 1" @click="goPage(storeQuery.page - 1)">上一页</button>
        <span class="pager-info">第 {{ storeQuery.page }} / {{ totalPages }} 页</span>
        <button class="btn" type="button" :disabled="storeQuery.page >= totalPages" @click="goPage(storeQuery.page + 1)">下一页</button>
      </div>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 调整换花规矩 -->
    <div v-if="rulesOpen" class="modal-mask" @click.self="rulesOpen = false">
      <div class="modal">
        <h3>调整换花规矩（按花期阶段设定换花周期）</h3>
        <p class="page-desc">保存后全部在册造景将按新规矩重算换花优先级，列表与概览页同步生效。</p>
        <table class="rules-table">
          <thead><tr><th>花期阶段</th><th>换花周期（天）</th></tr></thead>
          <tbody>
            <tr v-for="phase in meta?.phases ?? []" :key="phase">
              <td>{{ phase }}</td>
              <td><input v-model.number="ruleDraft[phase]" type="number" min="1" max="365" /></td>
            </tr>
          </tbody>
        </table>
        <p v-if="rulesError" class="error-text">{{ rulesError }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="rulesOpen = false">取消</button>
          <button class="btn primary" type="button" :disabled="savingRules" @click="saveRules">{{ savingRules ? '重算中…' : '保存并重算优先级' }}</button>
        </div>
      </div>
    </div>

    <!-- 登记花卉造景 -->
    <div v-if="createOpen" class="modal-mask" @click.self="createOpen = false">
      <div class="modal">
        <h3>登记花卉造景</h3>
        <p class="page-desc">同一造景编号重复登记时，列表自动只保留登记时间最新的一版；缺面积或品种的新版也会先被过滤并出现在对账明细里。</p>
        <div class="form-grid">
          <label v-for="field in createFields" :key="field.key">
            <span>{{ field.label }}{{ field.required ? ' *' : '' }}</span>
            <input v-model="createDraft[field.key]" :placeholder="field.placeholder" />
          </label>
        </div>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="createOpen = false">取消</button>
          <button class="btn primary" type="button" :disabled="creating" @click="submitCreate">{{ creating ? '提交中…' : '登记' }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script lang="ts">
// 显式组件名，供 App.vue 的 KeepAlive include 精确缓存列表页（详情返回时保留条件/页码/滚动）
export default { name: 'FlowerList' }
</script>

<script setup lang="ts">
import { computed, nextTick, onActivated, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import {
  DEFAULT_QUERY,
  useFlowerStore,
  type FlowerQuery,
  type FlowerRow,
  type ListResult,
} from '@/stores/flower'

const flowerStore = useFlowerStore()
const { query: storeQuery, meta } = storeToRefs(flowerStore)
const route = useRoute()
const router = useRouter()

const result = ref<ListResult | null>(null)
const errorMessage = ref('')
const showMerged = ref(false)
const showFiltered = ref(false)
const recomputeNotice = ref('')

// 表单里正在编辑的条件（点“查询”后才落到共享 query 与 URL）
const draft = reactive<FlowerQuery>({ ...flowerStore.query })
watch(storeQuery, (query) => {
  Object.assign(draft, query)
}, { deep: true })

const rows = computed<FlowerRow[]>(() => result.value?.items ?? [])
const summary = computed(() => result.value?.summary ?? null)
const totalPages = computed(() =>
  Math.max(1, Math.ceil((result.value?.total ?? 0) / (result.value?.size || flowerStore.query.size))),
)
const hasActiveFilter = computed(() =>
  Boolean(storeQuery.value.region || storeQuery.value.phase || storeQuery.value.priority || storeQuery.value.keyword),
)
const activeFilterText = computed(() =>
  [storeQuery.value.region, storeQuery.value.phase, storeQuery.value.priority, storeQuery.value.keyword]
    .filter(Boolean)
    .join(' / '),
)

function tierClass(tier: string): string {
  return { 已逾期: 'overdue', 紧急: 'urgent', 偏紧: 'tight', 正常: 'normal', 宽松: 'loose' }[tier] ?? 'normal'
}

function queryFromRoute(): FlowerQuery {
  const q = route.query
  return {
    region: String(q.region ?? ''),
    phase: String(q.phase ?? ''),
    priority: String(q.priority ?? ''),
    keyword: String(q.keyword ?? ''),
    page: Number(q.page ?? 1) || 1,
    size: Number(q.size ?? DEFAULT_QUERY.size) || DEFAULT_QUERY.size,
  }
}

function syncUrl(query: FlowerQuery) {
  const params: Record<string, string> = {}
  if (query.region) params.region = query.region
  if (query.phase) params.phase = query.phase
  if (query.priority) params.priority = query.priority
  if (query.keyword) params.keyword = query.keyword
  if (query.page > 1) params.page = String(query.page)
  if (query.size !== DEFAULT_QUERY.size) params.size = String(query.size)
  void router.replace({ name: 'flower', query: params })
}

async function reload() {
  errorMessage.value = ''
  syncUrl(flowerStore.query)
  Object.assign(draft, flowerStore.query)
  try {
    result.value = await flowerStore.fetchList(flowerStore.query)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '花卉造景列表读取失败'
  }
}

function applyFilters() {
  flowerStore.setQuery({
    region: draft.region.trim(),
    phase: draft.phase,
    priority: draft.priority,
    keyword: draft.keyword.trim(),
  })
  void reload()
}

function resetFilters() {
  flowerStore.setQuery({ ...DEFAULT_QUERY })
  void reload()
}

function goPage(page: number) {
  flowerStore.setQuery({ page: Math.min(Math.max(1, page), totalPages.value) })
  void reload()
}

// 浏览器前进/后退（URL 变化）也要跟着换条件并锁定对应页
watch(() => route.fullPath, () => {
  if (route.name !== 'flower') return
  const incoming = queryFromRoute()
  if (JSON.stringify(incoming) !== JSON.stringify({ ...flowerStore.query })) {
    flowerStore.query.region = incoming.region
    flowerStore.query.phase = incoming.phase
    flowerStore.query.priority = incoming.priority
    flowerStore.query.keyword = incoming.keyword
    flowerStore.query.size = incoming.size
    flowerStore.query.page = incoming.page
    void reload()
  }
})

function detailLink(id: number) {
  // 点击瞬间记下滚动位置；条件与页码始终留在 URL 与共享 store 里，返回时凭它们回到原位置
  cachedScroll = snapshotScroll()
  return { name: 'flower-detail', params: { id }, query: { ...route.query } }
}

function snapshotScroll(): number {
  return window.scrollY
}

function exportRows() {
  const params = new URLSearchParams()
  if (flowerStore.query.region) params.set('region', flowerStore.query.region)
  if (flowerStore.query.phase) params.set('phase', flowerStore.query.phase)
  window.open(`/api/flower/export/all?${params.toString()}`, '_blank')
}

async function markChanged(row: FlowerRow) {
  errorMessage.value = ''
  try {
    await flowerStore.markChanged(row.id)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '安排换花失败'
  }
}

// —— 规矩弹窗 ——
const rulesOpen = ref(false)
const savingRules = ref(false)
const rulesError = ref('')
const ruleDraft = reactive<Record<string, number>>({})

async function openRules() {
  rulesError.value = ''
  try {
    const rules = await flowerStore.fetchRules()
    Object.keys(rules.周期天数).forEach((phase) => {
      ruleDraft[phase] = rules.周期天数[phase]
    })
    rulesOpen.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '换花规矩读取失败'
  }
}

async function saveRules() {
  rulesError.value = ''
  savingRules.value = true
  try {
    await flowerStore.updateRules({ ...ruleDraft })
    rulesOpen.value = false
    recomputeNotice.value = flowerStore.lastRecomputeMessage
    await reload()
  } catch (error) {
    rulesError.value = error instanceof Error ? error.message : '换花规矩保存失败'
  } finally {
    savingRules.value = false
  }
}

// —— 登记弹窗 ——
const createOpen = ref(false)
const creating = ref(false)
const createError = ref('')
const createFields = [
  { key: '造景编号', label: '造景编号', required: true, placeholder: 'FLOW-0018' },
  { key: '造景主题', label: '造景主题', required: true, placeholder: '如 湖滨秋季花境' },
  { key: '所在区域', label: '所在区域', required: true, placeholder: '如 东湖滨水区' },
  { key: '花卉品种', label: '花卉品种', required: false, placeholder: '缺品种会被列表过滤' },
  { key: '景观面积', label: '景观面积(㎡)', required: false, placeholder: '缺面积会被列表过滤' },
  { key: '花期起', label: '花期起', required: false, placeholder: 'YYYY-MM-DD' },
  { key: '花期止', label: '花期止', required: false, placeholder: 'YYYY-MM-DD' },
  { key: '上次换花日', label: '上次换花日', required: false, placeholder: 'YYYY-MM-DD' },
  { key: '养护人员', label: '养护人员', required: false, placeholder: '负责人姓名' },
]
const createDraft = reactive<Record<string, string>>({})

function openCreate() {
  createFields.forEach((field) => { createDraft[field.key] = '' })
  createError.value = ''
  createOpen.value = true
}

async function submitCreate() {
  createError.value = ''
  creating.value = true
  try {
    await flowerStore.createEntry({ ...createDraft })
    createOpen.value = false
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '花卉造景登记失败'
  } finally {
    creating.value = false
  }
}

// —— KeepAlive：首次挂载按 URL 条件初始化；从详情返回时停留原位置 ——
onMounted(() => {
  const incoming = queryFromRoute()
  flowerStore.query.region = incoming.region
  flowerStore.query.phase = incoming.phase
  flowerStore.query.priority = incoming.priority
  flowerStore.query.keyword = incoming.keyword
  flowerStore.query.size = incoming.size
  flowerStore.query.page = incoming.page
  void flowerStore.fetchMeta().catch(() => undefined)
  void reload()
})

let cachedScroll = 0
onActivated(() => {
  // 从详情返回：条件与页码都保留在 store 里，这里只恢复滚动位置
  nextTick(() => window.scrollTo(0, cachedScroll))
})

onDeactivated(() => {
  // RouterLink 触发离开前先快照滚动位置
  cachedScroll = snapshotScroll()
})
</script>
