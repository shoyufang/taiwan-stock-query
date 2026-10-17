import { describe, expect, it } from 'vitest'
import { buildPositions, taxRate, totals, type Holding } from './portfolio'

const h = (id: number, code: string, shares: number, cost: number): Holding => ({ id, code, shares, cost, bought_on: null, note: '', created_at: '' })

describe('taxRate', () => {
  it('股票、ETF、債券 ETF', () => {
    expect(taxRate('2330')).toBe(0.003)
    expect(taxRate('0050')).toBe(0.001)
    expect(taxRate('00679B')).toBe(0)
  })
})

describe('buildPositions', () => {
  const holdings = [h(1, '2330', 1000, 1000), h(2, '2330', 500, 1300), h(3, '0050', 2000, 150), h(4, '2317', 1000, 200)]
  const quotes = { '2330': { code: '2330', name: '台積電', date: '2026-10-16' }, '0050': { code: '0050', name: '元大台灣50', date: '2026-10-16' } }
  const prices = { '2330': { close: 1200, change: -20, live: true }, '0050': { close: 160, change: 1, live: false } }
  const ps = buildPositions(holdings, quotes, prices)

  it('合併多筆買進、加權平均成本、依市值排序', () => {
    const tsmc = ps[0]
    expect(tsmc.code).toBe('2330')
    expect(tsmc.shares).toBe(1500)
    expect(tsmc.avgCost).toBe(1100)
    expect(tsmc.marketValue).toBe(1_800_000)
    expect(tsmc.pnl).toBe(150_000)
    expect(tsmc.dayChange).toBe(-30_000)
    // 手續費 0.1425% + 證交稅 0.3%
    expect(tsmc.sellCost).toBe(2565 + 5400)
    expect(tsmc.live).toBe(true)
    expect(ps.map((p) => p.code)).toEqual(['2330', '0050', '2317'])
  })

  it('沒有報價的部位不算進合計，並回報缺幾檔', () => {
    const noPrice = ps.find((p) => p.code === '2317')!
    expect(noPrice.marketValue).toBeNull()
    expect(noPrice.name).toBe('2317')
    const t = totals(ps)
    expect(t.missing).toBe(1)
    expect(t.marketValue).toBe(1_800_000 + 320_000)
    expect(t.costBasis).toBe(1_650_000 + 300_000)
    expect(t.pnl).toBe(170_000)
    expect(t.netPnl).toBe(170_000 - (2565 + 5400) - (456 + 320))
    expect(ps[0].weight! + ps[1].weight!).toBeCloseTo(100)
  })
})
