// 選股篩選（在瀏覽器做，條件即時生效）

export interface ScreenRow {
  code: string
  name: string
  industry: string
  close: number
  change_pct: number
  value_e8: number
  pe: number | null
  dividend_yield: number | null
  pb: number | null
  foreign: number
  trust: number
  dealer: number
  foreign_streak: number
  trust_streak: number
}

export interface Filters {
  priceMin?: number
  priceMax?: number
  pctMin?: number
  pctMax?: number
  valueMin?: number
  peMax?: number
  yieldMin?: number
  pbMax?: number
  foreignMin?: number
  trustMin?: number
  foreignStreakMin?: number
  trustStreakMin?: number
  industry?: string
}

export const PRESETS: { key: string; label: string; hint: string; filters: Filters }[] = [
  { key: 'dual', label: '外資投信雙買超', hint: '外資與投信當日同步買超', filters: { foreignMin: 1, trustMin: 1 } },
  { key: 'value', label: '高殖利率低本益比', hint: '本益比 ≤ 15 且殖利率 ≥ 4%', filters: { peMax: 15, yieldMin: 4 } },
  { key: 'fstreak', label: '外資連買 3 天以上', hint: '外資連續買超 ≥ 3 個交易日', filters: { foreignStreakMin: 3 } },
  { key: 'tstreak', label: '投信連買 3 天以上', hint: '投信連續買超 ≥ 3 個交易日', filters: { trustStreakMin: 3 } },
  { key: 'strong', label: '強勢量大', hint: '漲幅 ≥ 3% 且成交值 ≥ 5 億', filters: { pctMin: 3, valueMin: 5 } },
]

const ge = (v: number | null, min?: number) => min == null || (v != null && v >= min)
const le = (v: number | null, max?: number) => max == null || (v != null && v <= max)

export function applyFilters(rows: ScreenRow[], f: Filters): ScreenRow[] {
  return rows.filter(
    (r) =>
      ge(r.close, f.priceMin) &&
      le(r.close, f.priceMax) &&
      ge(r.change_pct, f.pctMin) &&
      le(r.change_pct, f.pctMax) &&
      ge(r.value_e8, f.valueMin) &&
      le(r.pe, f.peMax) &&
      ge(r.dividend_yield, f.yieldMin) &&
      le(r.pb, f.pbMax) &&
      ge(r.foreign, f.foreignMin) &&
      ge(r.trust, f.trustMin) &&
      ge(r.foreign_streak, f.foreignStreakMin) &&
      ge(r.trust_streak, f.trustStreakMin) &&
      (!f.industry || r.industry === f.industry),
  )
}

export type SortKey = keyof Pick<ScreenRow, 'change_pct' | 'value_e8' | 'pe' | 'dividend_yield' | 'pb' | 'foreign' | 'trust' | 'foreign_streak' | 'trust_streak' | 'close'>

export function sortRows(rows: ScreenRow[], key: SortKey, desc: boolean): ScreenRow[] {
  return [...rows].sort((a, b) => {
    const x = a[key]
    const y = b[key]
    if (x == null && y == null) return 0
    if (x == null) return 1 // 沒有數值的永遠排最後
    if (y == null) return -1
    return desc ? y - x : x - y
  })
}
