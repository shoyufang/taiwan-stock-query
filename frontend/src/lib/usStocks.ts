export interface UsStockRow {
  symbol: string
  name: string
  en_name: string
  sector: string
  date: string | null
  close: number
  change: number
  change_pct: number
  market_cap_b: number | null
  pe: number | null
  forward_pe: number | null
  pb: number | null
  dividend_yield: number
  high_52w: number
  low_52w: number
  pullback_pct: number
  above_ma50: boolean | null
  above_ma200: boolean | null
  eps_ttm: number | null
  eps_current_year: number | null
  eps_forward: number | null
  rating_score: number | null
  rating_label: string | null
  earnings_date: string | null
  earnings_is_estimate: boolean
}

export interface UsStocksData {
  asof: string
  today: string
  generated_at: string
  sectors: string[]
  rows: UsStockRow[]
  upcoming_earnings: UsStockRow[]
  sources: string[]
  note: string
}

export interface UsFilters {
  sector: string
  minMcapB: number | null
  maxPe: number | null
  maxForwardPe: number | null
  minYield: number | null
  pullbackMin: number | null
  pullbackMax: number | null
  maxRating: number | null
  aboveMa200: boolean
}

export const DEFAULT_US_FILTERS: UsFilters = {
  sector: '',
  minMcapB: null,
  maxPe: null,
  maxForwardPe: null,
  minYield: null,
  pullbackMin: null,
  pullbackMax: null,
  maxRating: null,
  aboveMa200: false,
}

export const US_PRESETS: { id: string; label: string; filters: Partial<UsFilters> }[] = [
  { id: 'all', label: '全部（50）', filters: {} },
  { id: 'm7', label: '科技巨頭 M7', filters: { sector: '科技巨頭' } },
  { id: 'semi', label: 'AI 與半導體', filters: { sector: '半導體' } },
  { id: 'value', label: '合理估值（前瞻 PE ≤ 25）', filters: { maxForwardPe: 25 } },
  { id: 'pullback', label: '高點拉回（−25% ～ −5%）', filters: { pullbackMin: -25, pullbackMax: -5 } },
  { id: 'strong_buy', label: '華爾街強買（評等 ≤ 1.8）', filters: { maxRating: 1.8 } },
  { id: 'dividend', label: '高股息（殖利率 ≥ 2%）', filters: { minYield: 2 } },
]

export type UsSortKey = 'market_cap_b' | 'change_pct' | 'pe' | 'forward_pe' | 'dividend_yield' | 'pullback_pct' | 'rating_score'

export function filterUsStocks(rows: UsStockRow[], f: UsFilters): UsStockRow[] {
  return rows.filter((r) => {
    if (f.sector && r.sector !== f.sector) return false
    if (f.minMcapB != null && (r.market_cap_b == null || r.market_cap_b < f.minMcapB)) return false
    if (f.maxPe != null && (r.pe == null || r.pe > f.maxPe)) return false
    if (f.maxForwardPe != null && (r.forward_pe == null || r.forward_pe > f.maxForwardPe)) return false
    if (f.minYield != null && r.dividend_yield < f.minYield) return false
    if (f.pullbackMin != null && r.pullback_pct < f.pullbackMin) return false
    if (f.pullbackMax != null && r.pullback_pct > f.pullbackMax) return false
    if (f.maxRating != null && (r.rating_score == null || r.rating_score > f.maxRating)) return false
    if (f.aboveMa200 && !r.above_ma200) return false
    return true
  })
}

export function sortUsStocks(rows: UsStockRow[], key: UsSortKey, asc: boolean): UsStockRow[] {
  return [...rows].sort((a, b) => {
    const va = a[key]
    const vb = b[key]
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    return asc ? va - vb : vb - va
  })
}
