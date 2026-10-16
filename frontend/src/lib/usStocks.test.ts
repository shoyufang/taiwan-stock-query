import { describe, expect, it } from 'vitest'
import { DEFAULT_US_FILTERS, filterUsStocks, sortUsStocks, type UsStockRow } from './usStocks'

const sample: UsStockRow[] = [
  {
    symbol: 'AAPL',
    name: '蘋果',
    en_name: 'Apple Inc.',
    sector: '科技巨頭',
    date: '2026-10-16',
    close: 343.46,
    change: 1.46,
    change_pct: 0.43,
    market_cap_b: 5012.5,
    pe: 39.39,
    forward_pe: 35.86,
    pb: 46.67,
    dividend_yield: 0.32,
    high_52w: 348.15,
    low_52w: 243.42,
    pullback_pct: -1.35,
    above_ma50: true,
    above_ma200: true,
    eps_ttm: 8.72,
    eps_current_year: 8.83,
    eps_forward: 9.58,
    rating_score: 2.2,
    rating_label: '買進',
    earnings_date: '2026-10-30',
    earnings_is_estimate: false,
  },
  {
    symbol: 'JPM',
    name: '摩根大通',
    en_name: 'JPMorgan',
    sector: '金融與支付',
    date: '2026-10-16',
    close: 339.72,
    change: -1.2,
    change_pct: -0.35,
    market_cap_b: 920.0,
    pe: 15.2,
    forward_pe: 14.5,
    pb: 2.4,
    dividend_yield: 2.1,
    high_52w: 370.0,
    low_52w: 260.0,
    pullback_pct: -8.18,
    above_ma50: false,
    above_ma200: true,
    eps_ttm: 22.3,
    eps_current_year: 22.8,
    eps_forward: 23.4,
    rating_score: 1.7,
    rating_label: '強力買進',
    earnings_date: '2027-01-14',
    earnings_is_estimate: true,
  },
]

describe('filterUsStocks & sortUsStocks', () => {
  it('按板塊、前瞻本益比、拉回區間與評等篩選', () => {
    expect(filterUsStocks(sample, { ...DEFAULT_US_FILTERS, sector: '科技巨頭' }).map((r) => r.symbol)).toEqual(['AAPL'])
    expect(filterUsStocks(sample, { ...DEFAULT_US_FILTERS, maxForwardPe: 20 }).map((r) => r.symbol)).toEqual(['JPM'])
    expect(filterUsStocks(sample, { ...DEFAULT_US_FILTERS, pullbackMin: -15, pullbackMax: -5 }).map((r) => r.symbol)).toEqual(['JPM'])
    expect(filterUsStocks(sample, { ...DEFAULT_US_FILTERS, maxRating: 1.8 }).map((r) => r.symbol)).toEqual(['JPM'])
  })

  it('依指定欄位排序並把空值排在最後', () => {
    expect(sortUsStocks(sample, 'pe', true).map((r) => r.symbol)).toEqual(['JPM', 'AAPL'])
    expect(sortUsStocks(sample, 'market_cap_b', false).map((r) => r.symbol)).toEqual(['AAPL', 'JPM'])
  })
})
