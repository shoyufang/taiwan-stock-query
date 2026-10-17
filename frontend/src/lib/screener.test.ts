import { describe, expect, it } from 'vitest'
import { applyFilters, applyFunnel, PRESETS, sortRows, type ScreenRow } from './screener'

const row = (o: Partial<ScreenRow>): ScreenRow => ({
  code: '1',
  name: 'n',
  industry: '半導體業',
  in_tw50: false,
  close: 100,
  change_pct: 0,
  value_e8: 1,
  vol_lots: 2000,
  pe: 10,
  dividend_yield: 5,
  pb: 1,
  rev_yoy: 15,
  foreign: 0,
  trust: 0,
  dealer: 0,
  total_inst: 0,
  foreign_streak: 0,
  trust_streak: 0,
  tech_signals: [],
  ...o,
})

describe('applyFilters & applyFunnel', () => {
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

  it('技術訊號 OR 與 AND 模式', () => {
    const rows = [
      row({ code: 'a', tech_signals: ['kd_golden'] }),
      row({ code: 'b', tech_signals: ['kd_golden', 'vol_breakout'] }),
      row({ code: 'c', tech_signals: ['rsi_oversold'] }),
    ]
    expect(applyFilters(rows, { techSignals: ['kd_golden', 'vol_breakout'], techMode: 'OR' }).map((r) => r.code)).toEqual(['a', 'b'])
    expect(applyFilters(rows, { techSignals: ['kd_golden', 'vol_breakout'], techMode: 'AND' }).map((r) => r.code)).toEqual(['b'])
  })

  it('多因子漏斗逐步計數（母體 → 技術面 → 籌碼面 → 基本面）', () => {
    const rows = [
      row({ code: '2330', in_tw50: true, tech_signals: ['ma_bullish'], foreign: 100, total_inst: 120, pe: 18, rev_yoy: 30 }),
      row({ code: '2454', in_tw50: true, tech_signals: ['ma_bullish'], foreign: -50, total_inst: -30, pe: 16, rev_yoy: 20 }),
      row({ code: '2303', in_tw50: true, tech_signals: ['ma_bullish'], foreign: 80, total_inst: 90, pe: 25, rev_yoy: 5 }),
      row({ code: '3008', in_tw50: true, tech_signals: [], foreign: 10, total_inst: 10, pe: 12, rev_yoy: 25 }),
      row({ code: '9999', in_tw50: false, tech_signals: ['ma_bullish'], foreign: 50, total_inst: 50, pe: 10, rev_yoy: 40 }),
    ]
    const res = applyFunnel(rows, {
      pool: 'tw50',
      techSignals: ['ma_bullish'],
      chipSignals: ['total_buy'],
      peMax: 20,
      revYoyMin: 15,
    })
    expect(res.funnel).toEqual({
      total: 5,
      pool: 4,
      afterTech: 3,
      afterChip: 2,
      final: 1,
    })
    expect(res.rows.map((r) => r.code)).toEqual(['2330'])
  })
})

describe('sortRows', () => {
  it('空值排最後', () => {
    const out = sortRows([row({ code: 'a', pe: null }), row({ code: 'b', pe: 5 }), row({ code: 'c', pe: 9 })], 'pe', false)
    expect(out.map((r) => r.code)).toEqual(['b', 'c', 'a'])
  })
})
