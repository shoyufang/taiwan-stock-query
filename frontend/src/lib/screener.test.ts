import { describe, expect, it } from 'vitest'
import { applyFilters, PRESETS, sortRows, type ScreenRow } from './screener'

const row = (o: Partial<ScreenRow>): ScreenRow => ({
  code: '1', name: 'n', industry: '半導體業', close: 100, change_pct: 0, value_e8: 1, pe: 10, dividend_yield: 5, pb: 1,
  foreign: 0, trust: 0, dealer: 0, foreign_streak: 0, trust_streak: 0, ...o,
})

describe('applyFilters', () => {
  it('高殖利率低本益比：本益比為空（虧損）不入選', () => {
    const f = PRESETS.find((p) => p.key === 'value')!.filters
    const out = applyFilters([row({ code: 'a' }), row({ code: 'b', pe: null }), row({ code: 'c', pe: 20 })], f)
    expect(out.map((r) => r.code)).toEqual(['a'])
  })
  it('雙買超與連買', () => {
    const rows = [row({ code: 'a', foreign: 5, trust: 1 }), row({ code: 'b', foreign: 5, trust: 0 }), row({ code: 'c', foreign_streak: 4 })]
    expect(applyFilters(rows, { foreignMin: 1, trustMin: 1 }).map((r) => r.code)).toEqual(['a'])
    expect(applyFilters(rows, { foreignStreakMin: 3 }).map((r) => r.code)).toEqual(['c'])
  })
  it('產業篩選', () => {
    expect(applyFilters([row({ code: 'a' }), row({ code: 'b', industry: '航運業' })], { industry: '航運業' }).map((r) => r.code)).toEqual(['b'])
  })
})

describe('sortRows', () => {
  it('空值排最後', () => {
    const out = sortRows([row({ code: 'a', pe: null }), row({ code: 'b', pe: 5 }), row({ code: 'c', pe: 9 })], 'pe', false)
    expect(out.map((r) => r.code)).toEqual(['b', 'c', 'a'])
  })
})
