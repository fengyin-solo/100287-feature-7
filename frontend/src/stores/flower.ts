import { defineStore } from 'pinia'

import { request } from '@/api/client'

/** 造景行：后端用中文字段名，前端保持同名便于表格直接渲染。 */
export type FlowerRow = {
  id: number
  造景编号: string
  造景主题: string
  所在区域: string
  花卉品种: string
  景观面积: number
  花期起: string
  花期止: string
  花期阶段: string
  换花周期天数: number
  下次换花日: string
  剩余天数: number
  换花优先级: string
  上次换花日?: string
  养护人员?: string
  造景状态?: string
  登记时间?: string
  已归档?: boolean
  [key: string]: string | number | boolean | null | undefined
}

export type FilteredOut = {
  id: number | null
  造景编号: string | null
  造景主题: string | null
  原因: string
  登记时间: string | null
}

export type MergedDup = {
  造景编号: string
  保留版本: string
  合并版本: string
}

export type FlowerSummary = {
  登记总条数: number
  重复合并条数: number
  缺字段过滤条数: number
  在册片数: number
  筛选片数: number
  本页片数: number
  重复合并明细: MergedDup[]
  缺字段过滤明细: FilteredOut[]
  规矩更新时间: string | null
  筛选条件: {
    区域: string | null
    花期阶段: string | null
    换花优先级: string | null
    关键词: string | null
  }
}

export type ListResult = {
  items: FlowerRow[]
  total: number
  page: number
  size: number
  summary: FlowerSummary
}

export type FlowerQuery = {
  region: string
  phase: string
  priority: string
  keyword: string
  page: number
  size: number
}

export type FlowerRules = {
  周期天数: Record<string, number>
  阶段区间: Record<string, [number, number]>
  更新时间: string | null
}

export type Meta = {
  regions: string[]
  phases: string[]
  priorities: string[]
  rules: FlowerRules
}

export const DEFAULT_QUERY: FlowerQuery = { region: '', phase: '', priority: '', keyword: '', page: 1, size: 8 }

function cacheKey(query: FlowerQuery): string {
  return JSON.stringify(query)
}

export const useFlowerStore = defineStore('flower', {
  state: () => ({
    /** 各页面共享的当前查询条件（切页/返回/跨页查看都以此为准）。 */
    query: { ...DEFAULT_QUERY } as FlowerQuery,
    cache: new Map<string, ListResult>(),
    inflight: new Map<string, Promise<ListResult>>(),
    meta: null as Meta | null,
    rules: null as FlowerRules | null,
    /** 最近一次规矩重算提示，保存后在列表页弹给用户看。 */
    lastRecomputeMessage: '',
  }),
  getters: {
    currentResult(state): ListResult | null {
      return state.cache.get(cacheKey(state.query)) ?? null
    },
  },
  actions: {
    setQuery(patch: Partial<FlowerQuery>) {
      const next = { ...this.query, ...patch }
      // 改条件时回到第一页；显式翻页时 page 单独传入。
      if (patch.page === undefined) next.page = 1
      this.query = next
    },
    /** 拉取同一份列表：相同条件并发只发一个请求，结果缓存供列表页与概览页共用。 */
    async fetchList(query?: FlowerQuery, force = false): Promise<ListResult> {
      const store = this
      const effectiveQuery = query ?? store.query
      const key = cacheKey(effectiveQuery)
      if (!force && store.cache.has(key)) return store.cache.get(key) as ListResult
      const pending = store.inflight.get(key)
      if (pending) return pending

      const params = new URLSearchParams()
      if (effectiveQuery.region) params.set('region', effectiveQuery.region)
      if (effectiveQuery.phase) params.set('phase', effectiveQuery.phase)
      if (effectiveQuery.priority) params.set('priority', effectiveQuery.priority)
      if (effectiveQuery.keyword) params.set('keyword', effectiveQuery.keyword)
      params.set('page', String(effectiveQuery.page))
      params.set('size', String(effectiveQuery.size))

      const promise = request(`/api/flower?${params.toString()}`)
        .then(async (response) => {
          if (!response.ok) {
            const payload = await response.json().catch(() => ({}))
            throw new Error(payload.detail ?? '花卉造景列表读取失败')
          }
          const result = (await response.json()) as ListResult
          store.cache.set(key, result)
          return result
        })
        .finally(() => {
          store.inflight.delete(key)
        })
      store.inflight.set(key, promise)
      return promise
    },
    async fetchMeta(force = false): Promise<Meta> {
      if (!force && this.meta) return this.meta
      const response = await request('/api/flower/meta')
      if (!response.ok) throw new Error('花卉筛选项读取失败')
      const meta = (await response.json()) as Meta
      this.meta = meta
      this.rules = meta.rules
      return meta
    },
    async fetchRules(): Promise<FlowerRules> {
      const response = await request('/api/flower/rules')
      if (!response.ok) throw new Error('换花规矩读取失败')
      this.rules = (await response.json()) as FlowerRules
      return this.rules
    },
    /** 改规矩：成功后清空全部列表缓存，保证之后任何页面拿到的都是按新规矩重算的同一份。 */
    async updateRules(cycles: Record<string, number>) {
      const response = await request('/api/flower/rules', {
        method: 'PUT',
        body: JSON.stringify({ cycles }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.detail ?? '换花规矩未保存')
      this.rules = payload.rules as FlowerRules
      if (this.meta) this.meta.rules = payload.rules as FlowerRules
      this.cache.clear()
      const recomputed = payload.recomputed as { 在册片数: number; 优先级变动片数: number }
      this.lastRecomputeMessage =
        `新规矩已生效：${recomputed.在册片数} 片在册造景全部重算，其中 ${recomputed.优先级变动片数} 片换花优先级发生变化。`
      return payload
    },
    async markChanged(id: number) {
      const response = await request(`/api/flower/${id}/actions`, {
        method: 'POST',
        body: JSON.stringify({ action: '安排换花' }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.message ?? payload.detail ?? '安排换花失败')
      }
      this.cache.clear()
      return payload
    },
    async createEntry(values: Record<string, string>) {
      const response = await request('/api/flower', {
        method: 'POST',
        body: JSON.stringify({ values }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.message ?? payload.detail ?? '花卉造景登记失败')
      }
      this.cache.clear()
      if (this.meta) void this.fetchMeta(true)
      return payload
    },
  },
})
