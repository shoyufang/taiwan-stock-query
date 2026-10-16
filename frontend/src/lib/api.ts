// 後端 /api 回傳格式（與 backend/app/services/overview.py 對應）。

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

export class NotReadyError extends Error {}

export async function fetchOverview(): Promise<Overview> {
  const res = await fetch('/api/market/overview', { cache: 'no-store' })
  if (res.status === 503) throw new NotReadyError('資料準備中')
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}
