// 選股與技術掃描引擎（瀏覽器端即時多因子漏斗篩選：母體 → 技術面 → 籌碼面 → 估值與基本面）

export interface ScreenRow {
  code: string
  name: string
  industry: string
  in_tw50?: boolean
  close: number
  change_pct: number
  value_e8: number
  vol_lots?: number
  pe: number | null
  dividend_yield: number | null
  pb: number | null
  rev_yoy?: number | null
  rev_mom?: number | null
  rev_ym?: string | null
  foreign: number
  trust: number
  dealer: number
  total_inst?: number
  foreign_streak: number
  trust_streak: number
  dealer_streak?: number
  rsi14?: number | null
  k?: number | null
  d?: number | null
  macd_hist?: number | null
  ma5?: number | null
  ma10?: number | null
  ma20?: number | null
  ma60?: number | null
  vol_ratio?: number | null
  tech_signals?: string[]
}

export type LogicMode = 'OR' | 'AND'
export type PoolScope = 'all' | 'tw50'

export interface Filters {
  pool?: PoolScope
  priceMin?: number
  priceMax?: number
  pctMin?: number
  pctMax?: number
  valueMin?: number
  volLotsMin?: number
  techSignals?: string[]
  techMode?: LogicMode
  chipSignals?: string[]
  chipMode?: LogicMode
  foreignMin?: number
  trustMin?: number
  foreignStreakMin?: number
  trustStreakMin?: number
  peMax?: number
  yieldMin?: number
  pbMax?: number
  revYoyMin?: number
  industry?: string
}

export interface TechItem {
  key: string
  label: string
  shortLabel: string
  tone: 'up' | 'down' | 'neutral'
}

export const TECH_GROUPS: { group: string; items: TechItem[] }[] = [
  {
    group: '均線與趨勢',
    items: [
      { key: 'ma_bullish', label: '均線多頭排列 (MA5>10>20>60)', shortLabel: '均線多頭', tone: 'up' },
      { key: 'ma5_cross_ma20', label: 'MA5 黃金交叉 MA20', shortLabel: 'MA金叉', tone: 'up' },
      { key: 'high_20d', label: '突破 20 日高點', shortLabel: '破20日高', tone: 'up' },
      { key: 'ma_bearish', label: '均線空頭排列 (MA5<10<20<60)', shortLabel: '均線空頭', tone: 'down' },
      { key: 'ma5_death_ma20', label: 'MA5 死亡交叉 MA20', shortLabel: 'MA死叉', tone: 'down' },
    ],
  },
  {
    group: 'KD 與 RSI',
    items: [
      { key: 'kd_golden', label: 'KD 黃金交叉（低檔 K<50）', shortLabel: 'KD金叉', tone: 'up' },
      { key: 'kd_oversold', label: 'KD 超賣 (K < 20)', shortLabel: 'KD超賣', tone: 'neutral' },
      { key: 'rsi_oversold', label: 'RSI 超賣 (< 30)', shortLabel: 'RSI超賣', tone: 'neutral' },
      { key: 'kd_death', label: 'KD 死亡交叉（高檔 K>50）', shortLabel: 'KD死叉', tone: 'down' },
      { key: 'rsi_overbought', label: 'RSI 超買 (> 70)', shortLabel: 'RSI超買', tone: 'up' },
    ],
  },
  {
    group: 'MACD 與布林',
    items: [
      { key: 'macd_golden', label: 'MACD 黃金交叉', shortLabel: 'MACD金叉', tone: 'up' },
      { key: 'macd_positive', label: 'MACD 柱狀翻正', shortLabel: 'MACD翻正', tone: 'up' },
      { key: 'bb_breakout', label: '布林突破上軌', shortLabel: '突破上軌', tone: 'up' },
      { key: 'bb_oversold', label: '布林觸下軌', shortLabel: '觸布林下軌', tone: 'neutral' },
      { key: 'macd_death', label: 'MACD 死亡交叉', shortLabel: 'MACD死叉', tone: 'down' },
    ],
  },
  {
    group: '量能異動',
    items: [
      { key: 'vol_breakout', label: '帶量突破 MA20 (>1.5x均量)', shortLabel: '帶量破月線', tone: 'up' },
      { key: 'vol_expand', label: '量增 (>1.5 倍 5 日均量)', shortLabel: '量增1.5x', tone: 'up' },
      { key: 'vol_2x', label: '爆量突破 (>2 倍 20 日均量)', shortLabel: '爆量2x', tone: 'up' },
    ],
  },
]

export const TECH_ITEM_MAP: Record<string, TechItem> = Object.fromEntries(
  TECH_GROUPS.flatMap((g) => g.items.map((item) => [item.key, item])),
)

export const CHIP_ITEMS: { key: string; label: string }[] = [
  { key: 'foreign_buy', label: '外資今日買超' },
  { key: 'trust_buy', label: '投信今日買超' },
  { key: 'dealer_buy', label: '自營商今日買超' },
  { key: 'total_buy', label: '三大法人合計買超' },
  { key: 'foreign_5d', label: '外資連 5 日買超' },
  { key: 'trust_3d', label: '投信連 3 日買超' },
]

export const PRESETS: { key: string; label: string; hint: string; filters: Filters }[] = [
  { key: 'dual', label: '外資投信雙買超', hint: '外資與投信當日同步買超', filters: { foreignMin: 1, trustMin: 1 } },
  { key: 'value', label: '高殖利率低本益比', hint: '本益比 ≤ 15 且殖利率 ≥ 4%', filters: { peMax: 15, yieldMin: 4 } },
  {
    key: 'tech_breakout',
    label: '帶量突破＋法人買',
    hint: '帶量突破 MA20 或突破 20 日高點，且三大法人合計買超',
    filters: { techSignals: ['vol_breakout', 'high_20d'], techMode: 'OR', chipSignals: ['total_buy'] },
  },
  {
    key: 'kd_macd_growth',
    label: '技術轉強＋營收成長',
    hint: 'KD 低檔金叉、MACD 金叉或柱狀翻正，且月營收年增率 ≥ 10%',
    filters: { techSignals: ['kd_golden', 'macd_golden', 'macd_positive'], techMode: 'OR', revYoyMin: 10 },
  },
  {
    key: 'oversold_value',
    label: '超賣高息價值股',
    hint: 'RSI < 30 或 KD < 20 或觸布林下軌，且殖利率 ≥ 4%、本益比 ≤ 20',
    filters: { techSignals: ['rsi_oversold', 'kd_oversold', 'bb_oversold'], techMode: 'OR', yieldMin: 4, peMax: 20 },
  },
  {
    key: 'tw50_bull',
    label: '台灣 50 均線多頭',
    hint: '台灣 50 權值股且均線呈多頭排列',
    filters: { pool: 'tw50', techSignals: ['ma_bullish'] },
  },
  { key: 'fstreak', label: '外資連買 3 天以上', hint: '外資連續買超 ≥ 3 個交易日', filters: { foreignStreakMin: 3 } },
  { key: 'tstreak', label: '投信連買 3 天以上', hint: '投信連續買超 ≥ 3 個交易日', filters: { trustStreakMin: 3 } },
  { key: 'strong', label: '強勢量大', hint: '漲幅 ≥ 3% 且成交值 ≥ 5 億', filters: { pctMin: 3, valueMin: 5 } },
]

const ge = (v: number | null | undefined, min?: number) => min == null || (v != null && v >= min)
const le = (v: number | null | undefined, max?: number) => max == null || (v != null && v <= max)

function matchChipSignal(r: ScreenRow, sig: string): boolean {
  const total = r.total_inst ?? r.foreign + r.trust + r.dealer
  switch (sig) {
    case 'foreign_buy':
      return r.foreign > 0
    case 'trust_buy':
      return r.trust > 0
    case 'dealer_buy':
      return r.dealer > 0
    case 'total_buy':
      return total > 0
    case 'foreign_5d':
      return r.foreign_streak >= 5
    case 'trust_3d':
      return r.trust_streak >= 3
    default:
      return false
  }
}

export interface FunnelResult {
  rows: ScreenRow[]
  funnel: {
    total: number
    pool: number
    afterTech: number
    afterChip: number
    final: number
  }
}

export function applyFunnel(rows: ScreenRow[], f: Filters): FunnelResult {
  const poolRows = rows.filter(
    (r) =>
      (f.pool !== 'tw50' || Boolean(r.in_tw50)) &&
      ge(r.close, f.priceMin) &&
      le(r.close, f.priceMax) &&
      ge(r.change_pct, f.pctMin) &&
      le(r.change_pct, f.pctMax) &&
      ge(r.value_e8, f.valueMin) &&
      ge(r.vol_lots ?? 0, f.volLotsMin),
  )

  const techConds = f.techSignals ?? []
  const techMode: LogicMode = f.techMode ?? 'OR'
  const afterTechRows =
    techConds.length === 0
      ? poolRows
      : poolRows.filter((r) => {
          const sigs = r.tech_signals ?? []
          return techMode === 'AND' ? techConds.every((c) => sigs.includes(c)) : techConds.some((c) => sigs.includes(c))
        })

  const chipConds = f.chipSignals ?? []
  const chipMode: LogicMode = f.chipMode ?? 'OR'
  const afterChipRows = afterTechRows.filter((r) => {
    const passSignals =
      chipConds.length === 0
        ? true
        : chipMode === 'AND'
          ? chipConds.every((c) => matchChipSignal(r, c))
          : chipConds.some((c) => matchChipSignal(r, c))
    return (
      passSignals &&
      ge(r.foreign, f.foreignMin) &&
      ge(r.trust, f.trustMin) &&
      ge(r.foreign_streak, f.foreignStreakMin) &&
      ge(r.trust_streak, f.trustStreakMin)
    )
  })

  const finalRows = afterChipRows.filter(
    (r) =>
      le(r.pe, f.peMax) &&
      ge(r.dividend_yield, f.yieldMin) &&
      le(r.pb, f.pbMax) &&
      ge(r.rev_yoy, f.revYoyMin) &&
      (!f.industry || r.industry === f.industry),
  )

  return {
    rows: finalRows,
    funnel: {
      total: rows.length,
      pool: poolRows.length,
      afterTech: afterTechRows.length,
      afterChip: afterChipRows.length,
      final: finalRows.length,
    },
  }
}

export function applyFilters(rows: ScreenRow[], f: Filters): ScreenRow[] {
  return applyFunnel(rows, f).rows
}

export type SortKey = keyof Pick<
  ScreenRow,
  | 'change_pct'
  | 'value_e8'
  | 'vol_lots'
  | 'pe'
  | 'dividend_yield'
  | 'pb'
  | 'rev_yoy'
  | 'foreign'
  | 'trust'
  | 'total_inst'
  | 'foreign_streak'
  | 'trust_streak'
  | 'rsi14'
  | 'k'
  | 'vol_ratio'
  | 'close'
>

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
