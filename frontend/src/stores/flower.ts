import { defineStore } from 'pinia'

import { request } from '@/api/client'

export interface FlowerQualityItem {
  id: number
  造景编号: string
  造景主题: string
  reason: string
}

export interface FlowerQuality {
  registered_total: number
  available_total: number
  duplicate_total: number
  invalid_total: number
  duplicates: FlowerQualityItem[]
  invalid: FlowerQualityItem[]
  stage_counts: Record<string, number>
}

export interface FlowerListResponse {
  items: FlowerRow[]
  total: number
  page: number
  size: number
  registered_total: number
  available_total: number
  quality: FlowerQuality
}

export interface FlowerOptions {
  areas: string[]
  stages: string[]
}

export interface FlowerRow extends Record<string, string | number | null | undefined> {
  id: number
  造景编号: string
  造景主题: string
  花卉品种: string
  景观面积: string
  花期起止: string
  换花周期: string
  养护人员: string
  造景状态: string
  所在区域: string
  花期阶段: string
  换花周期天?: number | null
  换花优先级: string
}

export interface FlowerState {
  keyword: string
  area: string
  stage: string
  page: number
  size: number
  rows: FlowerRow[]
  total: number
  registeredTotal: number
  availableTotal: number
  quality: FlowerQuality | null
  options: FlowerOptions
  loaded: boolean
  loading: boolean
  errorMessage: string
  scrollY: number
  shouldRestoreScroll: boolean
}

const emptyQuality: FlowerQuality = {
  registered_total: 0,
  available_total: 0,
  duplicate_total: 0,
  invalid_total: 0,
  duplicates: [],
  invalid: [],
  stage_counts: {},
}

export const useFlowerStore = defineStore('flower', {
  state: (): FlowerState => ({
    keyword: '',
    area: '',
    stage: '',
    page: 1,
    size: 5,
    rows: [],
    total: 0,
    registeredTotal: 0,
    availableTotal: 0,
    quality: null,
    options: { areas: [], stages: [] },
    loaded: false,
    loading: false,
    errorMessage: '',
    scrollY: 0,
    shouldRestoreScroll: false,
  }),
  getters: {
    queryParams: (state) => {
      const params: Record<string, string | number> = {}
      if (state.keyword.trim()) params.keyword = state.keyword.trim()
      if (state.area) params.area = state.area
      if (state.stage) params.stage = state.stage
      if (state.page !== 1) params.page = state.page
      if (state.size !== 5) params.size = state.size
      return params
    },
    totalPages(state): number {
      return Math.max(1, Math.ceil(state.total / state.size))
    },
    qualityOrEmpty: (state): FlowerQuality => state.quality ?? emptyQuality,
  },
  actions: {
    setFiltersFromQuery(query: Record<string, unknown>) {
      this.keyword = typeof query.keyword === 'string' ? query.keyword : ''
      this.area = typeof query.area === 'string' ? query.area : ''
      this.stage = typeof query.stage === 'string' ? query.stage : ''
      this.page = Number(query.page ?? 1)
      this.size = Number(query.size ?? 5)
      if (!Number.isFinite(this.page) || this.page < 1) this.page = 1
      if (![5, 10, 20].includes(this.size)) this.size = 5
    },
    saveScrollPosition() {
      this.scrollY = window.scrollY
      this.shouldRestoreScroll = true
    },
    restoreScrollPosition() {
      if (!this.shouldRestoreScroll) return
      window.scrollTo({ top: this.scrollY })
      this.shouldRestoreScroll = false
    },
    async loadOptions() {
      if (this.options.areas.length || this.options.stages.length) return
      try {
        const response = await request('/api/flower/options')
        if (!response.ok) throw new Error('花卉筛选项读取失败')
        this.options = (await response.json()) as FlowerOptions
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '花卉筛选项读取失败'
      }
    },
    async loadRows() {
      this.loading = true
      this.errorMessage = ''
      try {
        const query = new URLSearchParams()
        Object.entries(this.queryParams).forEach(([key, value]) => query.set(key, String(value)))
        const response = await request(`/api/flower?${query.toString()}`)
        if (!response.ok) throw new Error('花卉造景列表读取失败')
        const payload = (await response.json()) as FlowerListResponse
        this.rows = payload.items
        this.total = payload.total
        this.page = payload.page
        this.size = payload.size
        this.registeredTotal = payload.registered_total
        this.availableTotal = payload.available_total
        this.quality = payload.quality
        this.loaded = true
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '花卉造景列表读取失败'
      } finally {
        this.loading = false
      }
    },
    async runAction(action: string, row: FlowerRow) {
      this.errorMessage = ''
      try {
        const response = await request(`/api/flower/${row.id}/actions`, {
          method: 'POST',
          body: JSON.stringify({ values: { action } }),
        })
        const payload = (await response.json()) as { ok?: boolean; message?: string }
        if (!response.ok || payload.ok === false) {
          throw new Error(payload.message || '花卉造景动作未生效，请稍后重试')
        }
        await this.loadRows()
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '花卉造景操作失败'
      }
    },
  },
})
