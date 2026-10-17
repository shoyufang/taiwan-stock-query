export interface Holding {
  id: number
  code: string
  shares: number
  cost: number
  bought_on: string | null
  note: string
  created_at: string
}

export interface PortfolioQuote {
  code: string
  name: string
  date: string | null
  close?: number
  change?: number
}

export interface Price {
  close: number
  change: number
  live: boolean
}

export interface Position {
  code: string
  name: string
  lots: Holding[]
  shares: number
  avgCost: number
  costBasis: number
  price: number | null
  live: boolean
  marketValue: number | null
  pnl: number | null
  pnlPct: number | null
  dayChange: number | null
  sellCost: number | null
  weight: number | null
}

export const FEE_RATE = 0.001425

/** 證券交易稅：股票 0.3%；ETF（代號 00 開頭）0.1%；債券 ETF（00 開頭、B 結尾）停徵至 2026 年底。 */
export function taxRate(code: string): number {
  if (code.startsWith('00')) return code.endsWith('B') ? 0 : 0.001
  return 0.003
}

/** 依代號合併多筆買進：股數加總、加權平均成本；價格優先用即時成交，否則用最近收盤。 */
export function buildPositions(holdings: Holding[], quotes: Record<string, PortfolioQuote>, prices: Record<string, Price>): Position[] {
  const byCode = new Map<string, Holding[]>()
  for (const h of holdings) byCode.set(h.code, [...(byCode.get(h.code) ?? []), h])
  const out: Position[] = []
  for (const [code, lots] of byCode) {
    const shares = lots.reduce((s, h) => s + h.shares, 0)
    const costBasis = lots.reduce((s, h) => s + h.shares * h.cost, 0)
    const p = prices[code]
    const price = p ? p.close : null
    const mv = price === null ? null : price * shares
    const sellCost = mv === null ? null : Math.round(mv * FEE_RATE) + Math.round(mv * taxRate(code))
    out.push({
      code,
      name: quotes[code]?.name ?? code,
      lots,
      shares,
      avgCost: costBasis / shares,
      costBasis,
      price,
      live: p?.live ?? false,
      marketValue: mv,
      pnl: mv === null ? null : mv - costBasis,
      pnlPct: mv === null ? null : ((mv - costBasis) / costBasis) * 100,
      dayChange: p ? p.change * shares : null,
      sellCost,
      weight: null,
    })
  }
  const total = out.reduce((s, p) => s + (p.marketValue ?? 0), 0)
  for (const p of out) p.weight = p.marketValue !== null && total > 0 ? (p.marketValue / total) * 100 : null
  return out.sort((a, b) => (b.marketValue ?? 0) - (a.marketValue ?? 0))
}

export interface Totals {
  costBasis: number
  marketValue: number
  pnl: number
  pnlPct: number
  dayChange: number
  netPnl: number
  missing: number
}

/** 合計只納入有報價的部位；missing 為缺報價的檔數（頁面會提示）。 */
export function totals(positions: Position[]): Totals {
  const priced = positions.filter((p) => p.marketValue !== null)
  const costBasis = priced.reduce((s, p) => s + p.costBasis, 0)
  const marketValue = priced.reduce((s, p) => s + (p.marketValue ?? 0), 0)
  const pnl = marketValue - costBasis
  const sell = priced.reduce((s, p) => s + (p.sellCost ?? 0), 0)
  return {
    costBasis,
    marketValue,
    pnl,
    pnlPct: costBasis > 0 ? (pnl / costBasis) * 100 : 0,
    dayChange: priced.reduce((s, p) => s + (p.dayChange ?? 0), 0),
    netPnl: pnl - sell,
    missing: positions.length - priced.length,
  }
}
