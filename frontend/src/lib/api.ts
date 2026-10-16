// 後端 /api 回傳格式（與 backend/app/services/overview.py 對應）。

import type { Holding } from './portfolio'

export interface Quote {
  code: string
  name: string
  close: number
  change: number
  change_pct: number
  value_twd: number
}

export interface ForeignNet {
  code: string
  name: string
  lots: number
}

export interface IntlQuote {
  name: string
  symbol: string
  date: string
  close: number
  change_pct: number
}

export interface Overview {
  asof: string
  generated_at: string
  headline: string
  lead: string
  taiex: { close: number; change: number; change_pct: number }
  turnover_twd: number
  breadth: { up: number; up_limit: number; down: number; down_limit: number; flat: number; untraded?: number }
  institutional: { foreign: number; trust: number; dealer: number }
  top_value: Quote[]
  gainers: Quote[]
  losers: Quote[]
  foreign_buy: ForeignNet[]
  foreign_sell: ForeignNet[]
  index_series: { date: string; close: number }[]
  international: IntlQuote[]
  sources: string[]
}

export interface StockProfile {
  code: string
  name: string
  industry: string
  market: string
}

export interface StockPage {
  asof: string
  generated_at: string
  profile: StockProfile
  quote: {
    close: number
    open: number
    high: number
    low: number
    prev_close: number
    change: number
    change_pct: number
    volume: number
    value: number
    week52_high: number
    week52_low: number
  }
  report: { headline: string; lead: string; sections: Partial<Record<'institutional' | 'margin' | 'revenue' | 'valuation', string>> }
  institutional: { date: string; foreign: number; trust: number; dealer: number }[]
  margin: { date: string; margin_balance: number; margin_change: number; short_balance: number }[]
  revenue: { year: number; month: number; revenue: number; yoy: number | null; mom: number | null }[]
  valuation: {
    current: number
    min: number
    max: number
    median: number
    pct_rank: number
    days: number
    start: string
    end: string
    pbr: number | null
    dividend_yield: number | null
  } | null
  sources: string[]
}

export interface Bar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  value: number
}

export class NotFoundError extends Error {}

export async function fetchStock(code: string): Promise<StockPage> {
  const res = await fetch(`/api/stock/${encodeURIComponent(code)}`)
  if (res.status === 404) throw new NotFoundError(code)
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export async function fetchKbar(code: string, adjusted: boolean, years: number): Promise<Bar[]> {
  const res = await fetch(`/api/stock/${encodeURIComponent(code)}/kbar?adjusted=${adjusted}&years=${years}`)
  if (!res.ok) throw new Error(`API ${res.status}`)
  return (await res.json()).bars
}

export async function searchStocks(q: string): Promise<StockProfile[]> {
  const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`)
  if (!res.ok) return []
  return (await res.json()).results
}

// ── 自選股與警示 ──

export interface WatchRow {
  code: string
  name: string
  date: string | null
  close?: number
  change?: number
  change_pct?: number
  volume?: number
  high?: number
  low?: number
}

export interface Watchlist {
  codes: string[]
  is_default: boolean
  rows: WatchRow[]
}

export interface AlertRule {
  id: number
  code: string
  type: string
  value: number
  enabled: boolean
  created_at: string
  last_triggered_date: string | null
}

export interface AlertType {
  label: string
  when: 'intraday' | 'close'
  unit: string
  range: [number, number]
}

export interface AlertsResponse {
  rules: AlertRule[]
  types: Record<string, AlertType>
  channels: { web: boolean; ntfy: boolean; telegram: boolean }
}

export interface AlertEvent {
  id: number
  code: string
  type: string
  message: string
  at: string
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `API ${res.status}`
    try {
      const d = (await res.json()).detail
      // FastAPI 欄位驗證錯誤（422）的 detail 是陣列
      detail = Array.isArray(d) ? d.map((x) => String(x.msg ?? '')).join('；') || detail : (d ?? detail)
    } catch {
      // 非 JSON 錯誤
    }
    throw new Error(detail)
  }
  return res.json()
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

export const watchlistApi = {
  get: () => fetch('/api/watchlist').then((r) => json<Watchlist>(r)),
  put: (codes: string[]) => fetch('/api/watchlist', { method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify({ codes }) }).then((r) => json<{ codes: string[] }>(r)),
}

export const alertsApi = {
  list: () => fetch('/api/alerts').then((r) => json<AlertsResponse>(r)),
  add: (code: string, type: string, value: number) =>
    fetch('/api/alerts', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ code, type, value }) }).then((r) => json<{ id: number }>(r)),
  toggle: (id: number, enabled: boolean) =>
    fetch(`/api/alerts/${id}`, { method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify({ enabled }) }).then((r) => json(r)),
  remove: (id: number) => fetch(`/api/alerts/${id}`, { method: 'DELETE' }).then((r) => json(r)),
  events: () => fetch('/api/alerts/events?limit=30').then((r) => json<{ events: AlertEvent[] }>(r)),
  test: () => fetch('/api/alerts/test', { method: 'POST' }).then((r) => json<{ result: Record<string, boolean> }>(r)),
}

export class NotReadyError extends Error {}

export async function fetchOverview(): Promise<Overview> {
  const res = await fetch('/api/market/overview', { cache: 'no-store' })
  if (res.status === 503) throw new NotReadyError('資料準備中')
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export interface PortfolioData {
  holdings: Holding[]
  quotes: Record<string, WatchRow>
}

export interface HoldingIn {
  code: string
  shares: number
  cost: number
  bought_on: string | null
  note: string
}

export const portfolioApi = {
  get: () => fetch('/api/portfolio').then((r) => json<PortfolioData>(r)),
  add: (h: HoldingIn) => fetch('/api/portfolio', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(h) }).then((r) => json<{ id: number }>(r)),
  update: (id: number, h: HoldingIn) => fetch(`/api/portfolio/${id}`, { method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify(h) }).then((r) => json<{ ok: boolean }>(r)),
  remove: (id: number) => fetch(`/api/portfolio/${id}`, { method: 'DELETE' }).then((r) => json<{ ok: boolean }>(r)),
}
