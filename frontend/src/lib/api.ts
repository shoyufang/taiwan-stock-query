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

export class NotReadyError extends Error {}

export async function fetchOverview(): Promise<Overview> {
  const res = await fetch('/api/market/overview', { cache: 'no-store' })
  if (res.status === 503) throw new NotReadyError('資料準備中')
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}
